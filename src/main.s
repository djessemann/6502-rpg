; main.s — boot, split game loop, and NMI render pipeline (Step 1: Boot).
;
; Structural contract (CLAUDE.md), in place from the first ROM:
;   * Split loop: all game logic runs in the main thread; every PPU update
;     happens in the NMI handler.
;   * PPU discipline: $2005/$2006/$2007 are only touched inside NMI (or while
;     rendering is disabled during init). Per-frame nametable/palette changes
;     will go through the VRAM buffer at $0300 and be flushed in NMI.
;   * Shadow OAM at $0200, copied to the PPU by DMA every frame in NMI.
;   * A sound tick is called every frame, including lag frames (stub for now,
;     but the call site exists).

.include "nes.inc"

.import fieldmap, fieldattr, winmap

; ----------------------------------------------------------------------------
; Constants
; ----------------------------------------------------------------------------
MAX_ENT    = 8          ; entity array length (only the hero is used so far)
HERO       = 0          ; entity index of the hero

VBUF       = $0300      ; NMI VRAM buffer: one packet [hi, lo, count, data...]
                        ; hi = $00 means "no update this frame"

; Stationary NPC location, in 16px grid cells (must match tools/gen_assets.py)
NPC_GX     = 6
NPC_GY     = 6

; High-level game states
GS_FIELD   = 0          ; walking around
GS_OPENING = 1          ; wiping the text window in
GS_DIALOG  = 2          ; window shown, waiting to close
GS_CLOSING = 3          ; wiping the text window out
GS_BATTLE  = 4          ; encounter screen (placeholder until Step 6)

WIN_STEPS  = 9          ; 8 tile chunks + 1 attribute write

ENC_STEPS  = 16         ; grid steps before an encounter fires

; Facing / movement directions
DIR_UP     = 0
DIR_DOWN   = 1
DIR_LEFT   = 2
DIR_RIGHT  = 3

; Entity states
ST_IDLE    = 0
ST_MOVE    = 1

MOVE_SPEED = 2          ; pixels/frame while sliding (16 / 2 = 8 frames per cell)

; Solid (impassable) field tiles
TILE_TREE  = $04
TILE_WALL  = $05
TILE_WATER = $07
TILE_NPC_LO = $08       ; NPC tiles $08-$0B are solid

; Controller button bits (after the shift-in read order below)
BTN_A      = %10000000
BTN_B      = %01000000
BTN_SELECT = %00100000
BTN_START  = %00010000
BTN_UP     = %00001000
BTN_DOWN   = %00000100
BTN_LEFT   = %00000010
BTN_RIGHT  = %00000001

; ----------------------------------------------------------------------------
; Zeropage variables
; ----------------------------------------------------------------------------
.segment "ZEROPAGE"
frame_count:  .res 1   ; incremented by NMI; main loop syncs against it
ptr:          .res 2   ; general 16-bit pointer

pad1:         .res 1   ; controller 1, buttons held this frame
pad1_prev:    .res 1   ; buttons held last frame
pad1_new:     .res 1   ; buttons newly pressed this frame

; scratch for movement / collision (main-thread use only)
newgx:        .res 1
newgy:        .res 1
tpx:          .res 1
tpy:          .res 1
cs_gx:        .res 1
cs_gy:        .res 1
mt_col:       .res 1
mt_row:       .res 1

; dialog / window state (main-thread use only)
gamestate:    .res 1   ; GS_*
step_count:   .res 1   ; grid steps taken since the last encounter
job_step:     .res 1   ; current window draw step (0..WIN_STEPS-1)
draw_mode:    .res 1   ; 0 = opening (draw window), 1 = closing (restore field)
vpkt_lo:      .res 1   ; packet being built: PPU address low / count
vpkt_cnt:     .res 1

; ----------------------------------------------------------------------------
; Shadow OAM (DMA source page, $0200-$02FF)
; ----------------------------------------------------------------------------
.segment "OAMBUF"
oam:          .res 256

; ----------------------------------------------------------------------------
; Entities — struct-of-arrays, indexed by entity number (X register).
; ----------------------------------------------------------------------------
.segment "BSS"
ent_gx:    .res MAX_ENT   ; grid cell X (16px cells, 0..15)
ent_gy:    .res MAX_ENT   ; grid cell Y (0..14)
ent_px:    .res MAX_ENT   ; sprite pixel X (top-left)
ent_py:    .res MAX_ENT   ; sprite pixel Y (top-left)
ent_dir:   .res MAX_ENT   ; facing direction
ent_state: .res MAX_ENT   ; ST_IDLE / ST_MOVE
ent_timer: .res MAX_ENT   ; pixels remaining in the current slide

; ----------------------------------------------------------------------------
; RESET
; ----------------------------------------------------------------------------
.segment "CODE"
.proc RESET
    sei                 ; ignore IRQs
    cld                 ; NES has no decimal mode
    ldx #$40
    stx JOYPAD2         ; disable APU frame IRQ
    ldx #$FF
    txs                 ; set up stack
    inx                 ; X = 0
    stx PPUCTRL         ; disable NMI
    stx PPUMASK         ; disable rendering
    stx APUSTATUS       ; disable APU channels
    lda #$00
    sta $4010           ; disable DMC IRQ

    bit PPUSTATUS       ; clear any pending vblank
:   bit PPUSTATUS       ; wait for first vblank (PPU warm-up)
    bpl :-

    ; Clear all 2KB of internal RAM. Shadow OAM ($0200) is set to $FF so any
    ; unused sprite sits off-screen below the visible area.
    lda #$00
    ldx #$00
@clrmem:
    sta $0000,x
    sta $0100,x
    sta $0300,x
    sta $0400,x
    sta $0500,x
    sta $0600,x
    sta $0700,x
    lda #$FF
    sta $0200,x         ; OAM page -> off-screen
    lda #$00
    inx
    bne @clrmem

:   bit PPUSTATUS       ; wait for second vblank; PPU is now ready
    bpl :-

    ; Rendering is still off here, so direct VRAM writes are safe.
    lda #<pal_field
    sta ptr
    lda #>pal_field
    sta ptr+1
    jsr LoadPalette
    jsr DrawField
    jsr InitGame

    ; Enable NMI; background pattern table 0, sprite pattern table 1.
    lda #%10001000
    sta PPUCTRL
    ; Show background and sprites, including their leftmost 8px columns.
    lda #%00011110
    sta PPUMASK

    ; fall through into the main loop
.endproc

; ----------------------------------------------------------------------------
; MAIN — game logic thread. No PPU access here; ever.
; ----------------------------------------------------------------------------
.proc MAIN
@loop:
    jsr ReadInput
    jsr VBufClear       ; default: no nametable update this frame
    jsr UpdateGame      ; hero logic and/or a window draw step
    lda gamestate
    cmp #GS_BATTLE
    beq @hide
    jsr BuildOAM        ; field/dialog: draw the hero metasprite
    jmp @sync
@hide:
    jsr HideHero        ; battle screen: no field sprites
@sync:
    jsr WaitFrame       ; NMI flushes the VRAM buffer + OAM while we wait
    jmp @loop
.endproc

; Block until the NMI handler has run (one frame elapsed).
.proc WaitFrame
    lda frame_count
:   cmp frame_count
    beq :-
    rts
.endproc

; ----------------------------------------------------------------------------
; NMI — the only place PPU registers are written during the frame.
; ----------------------------------------------------------------------------
.proc NMI
    pha
    txa
    pha
    tya
    pha

    ; OAM DMA: copy shadow OAM ($0200) to the PPU.
    lda #$00
    sta OAMADDR
    lda #>OAM_BUF
    sta OAMDMA

    ; Flush the VRAM buffer: a single packet [hi, lo, count, data...].
    ; hi = $00 marks an empty buffer (no update this frame). Kept small enough
    ; (<= ~8 bytes) that the copy fits inside vblank alongside OAM DMA.
    lda VBUF
    beq @noflush
    sta PPUADDR
    lda VBUF+1
    sta PPUADDR
    ldx VBUF+2
    ldy #0
@flush:
    lda VBUF+3,y
    sta PPUDATA
    iny
    dex
    bne @flush
@noflush:

    ; Reset scroll after any potential $2006 write this frame.
    bit PPUSTATUS
    lda #$00
    sta PPUSCROLL
    sta PPUSCROLL
    lda #%10001000
    sta PPUCTRL

    jsr SoundTick       ; called every frame, including lag frames (stub)

    inc frame_count

    pla
    tay
    pla
    tax
    pla
    rti
.endproc

.proc IRQ
    rti
.endproc

; ----------------------------------------------------------------------------
; Sound tick — stubbed for the slice; the call site is what matters.
; ----------------------------------------------------------------------------
.proc SoundTick
    rts
.endproc

; ----------------------------------------------------------------------------
; InitGame — place the hero on the field. Other entity slots stay zeroed (RAM
; was cleared at reset), i.e. idle at cell (0,0); they are unused for now.
; ----------------------------------------------------------------------------
.proc InitGame
    ldx #HERO
    lda #4
    sta ent_gx,x        ; start on open grass, left-of-center
    lda #8
    sta ent_gy,x
    lda #4 * 16
    sta ent_px,x        ; pixel position = cell * 16
    lda #8 * 16
    sta ent_py,x
    lda #DIR_DOWN
    sta ent_dir,x
    lda #ST_IDLE
    sta ent_state,x

    lda #GS_FIELD
    sta gamestate
    rts
.endproc

; ----------------------------------------------------------------------------
; ReadInput — strobe controller 1, shift in 8 buttons, derive newly-pressed.
; ----------------------------------------------------------------------------
.proc ReadInput
    lda pad1
    sta pad1_prev

    lda #$01
    sta JOYPAD1         ; strobe on
    lda #$00
    sta JOYPAD1         ; strobe off; serial shift begins

    ldx #8
@read:
    lda JOYPAD1
    lsr a               ; button state -> carry
    rol pad1            ; shift into pad1 (first read = A -> ends in bit7)
    dex
    bne @read

    ; pad1_new = buttons set now that were not set last frame
    lda pad1_prev
    eor #$FF
    and pad1
    sta pad1_new
    rts
.endproc

; ----------------------------------------------------------------------------
; UpdateHero — idle: read the d-pad and try to start a step. Moving: slide.
; ----------------------------------------------------------------------------
.proc UpdateHero
    ldx #HERO
    lda ent_state,x
    cmp #ST_MOVE
    beq @moving

    ; idle: pick a direction from the held d-pad (up > down > left > right)
    lda pad1
    and #BTN_UP
    beq @notup
    ldy #DIR_UP
    jmp @try
@notup:
    lda pad1
    and #BTN_DOWN
    beq @notdown
    ldy #DIR_DOWN
    jmp @try
@notdown:
    lda pad1
    and #BTN_LEFT
    beq @notleft
    ldy #DIR_LEFT
    jmp @try
@notleft:
    lda pad1
    and #BTN_RIGHT
    beq @done
    ldy #DIR_RIGHT
@try:
    tya
    sta ent_dir,x       ; face that way even if the step is blocked
    jsr TryStep
    rts

@moving:
    jsr StepMove
@done:
    rts
.endproc

; Attempt to start a step in ent_dir,x. Commits the new cell (and enters the
; sliding state) only if the destination cell is in-bounds and not solid.
; X = entity index.
.proc TryStep
    lda ent_gx,x
    sta newgx
    lda ent_gy,x
    sta newgy

    lda ent_dir,x
    cmp #DIR_UP
    bne @nu
    dec newgy
    jmp @check
@nu:
    cmp #DIR_DOWN
    bne @nd
    inc newgy
    jmp @check
@nd:
    cmp #DIR_LEFT
    bne @nl
    dec newgx
    jmp @check
@nl:
    inc newgx           ; DIR_RIGHT

@check:
    ; bounds (unsigned: underflow wraps to a large value -> blocked)
    lda newgx
    cmp #16
    bcs @blocked
    lda newgy
    cmp #15
    bcs @blocked

    lda newgx
    sta cs_gx
    lda newgy
    sta cs_gy
    jsr CellSolid       ; carry set => solid
    bcs @blocked

    ; commit the move and begin the slide
    lda newgx
    sta ent_gx,x
    lda newgy
    sta ent_gy,x
    lda #ST_MOVE
    sta ent_state,x
    lda #16
    sta ent_timer,x
@blocked:
    rts
.endproc

; Slide the sprite toward its committed cell by MOVE_SPEED; finish when aligned.
; X = entity index.
.proc StepMove
    lda ent_gx,x        ; target pixel x = gx * 16
    asl a
    asl a
    asl a
    asl a
    sta tpx
    lda ent_gy,x        ; target pixel y = gy * 16
    asl a
    asl a
    asl a
    asl a
    sta tpy

    lda ent_px,x
    cmp tpx
    beq @ydiff
    bcc @xinc
    sec
    sbc #MOVE_SPEED
    sta ent_px,x
    jmp @ydiff
@xinc:
    clc
    adc #MOVE_SPEED
    sta ent_px,x

@ydiff:
    lda ent_py,x
    cmp tpy
    beq @tick
    bcc @yinc
    sec
    sbc #MOVE_SPEED
    sta ent_py,x
    jmp @tick
@yinc:
    clc
    adc #MOVE_SPEED
    sta ent_py,x

@tick:
    lda ent_timer,x
    sec
    sbc #MOVE_SPEED
    sta ent_timer,x
    bne @done
    lda #ST_IDLE
    sta ent_state,x     ; aligned on the grid again
    inc step_count      ; one completed grid step (hero only moves)
@done:
    rts
.endproc

; CellSolid — is the 16px grid cell (cs_gx,cs_gy) blocked? A cell spans a 2x2
; block of 8px map tiles; it is solid if ANY of those four tiles is solid.
; Returns carry set if solid. Preserves X.
.proc CellSolid
    lda cs_gx
    asl a
    sta mt_col          ; base map col = gx * 2
    lda cs_gy
    asl a
    sta mt_row          ; base map row = gy * 2

    jsr CheckTile       ; (col,   row)
    bcs @solid
    inc mt_col
    jsr CheckTile       ; (col+1, row)
    bcs @solid
    inc mt_row
    jsr CheckTile       ; (col+1, row+1)
    bcs @solid
    dec mt_col
    jsr CheckTile       ; (col,   row+1)
    bcs @solid
    clc
    rts
@solid:
    sec
    rts
.endproc

; CheckTile — read map tile (mt_col,mt_row); carry set if it is solid.
; Preserves X.
.proc CheckTile
    jsr MapTile
    cmp #TILE_TREE
    beq @solid
    cmp #TILE_WALL
    beq @solid
    cmp #TILE_WATER
    beq @solid
    cmp #TILE_NPC_LO    ; NPC occupies tiles $08-$0B (solid)
    bcc @walk
    cmp #TILE_NPC_LO + 4
    bcc @solid
@walk:
    clc
    rts
@solid:
    sec
    rts
.endproc

; MapTile — fetch fieldmap[mt_row*32 + mt_col] into A. Preserves X.
.proc MapTile
    lda #0
    sta ptr+1
    lda mt_row
    asl a
    rol ptr+1
    asl a
    rol ptr+1
    asl a
    rol ptr+1
    asl a
    rol ptr+1
    asl a
    rol ptr+1           ; ptr+1:A = mt_row * 32
    clc
    adc mt_col
    bcc :+
    inc ptr+1
:   clc
    adc #<fieldmap
    sta ptr
    lda ptr+1
    adc #>fieldmap
    sta ptr+1
    ldy #0
    lda (ptr),y
    rts
.endproc

; BuildOAM — write the hero's 4-tile metasprite into shadow OAM (entries 0-3).
; OAM byte order per sprite: Y, tile, attributes, X. Stored Y is screen-Y - 1.
.proc BuildOAM
    ldx #HERO

    ; top-left
    lda ent_py,x
    sec
    sbc #1
    sta oam+0
    lda #$00
    sta oam+1           ; sprite tile $00 (pattern table 1)
    lda #$00
    sta oam+2           ; palette 0, in front
    lda ent_px,x
    sta oam+3

    ; top-right
    lda ent_py,x
    sec
    sbc #1
    sta oam+4
    lda #$01
    sta oam+5
    lda #$00
    sta oam+6
    lda ent_px,x
    clc
    adc #8
    sta oam+7

    ; bottom-left  (screen-Y = py+8 -> stored py+7)
    lda ent_py,x
    clc
    adc #7
    sta oam+8
    lda #$02
    sta oam+9
    lda #$00
    sta oam+10
    lda ent_px,x
    sta oam+11

    ; bottom-right
    lda ent_py,x
    clc
    adc #7
    sta oam+12
    lda #$03
    sta oam+13
    lda #$00
    sta oam+14
    lda ent_px,x
    clc
    adc #8
    sta oam+15
    rts
.endproc

; ----------------------------------------------------------------------------
; VBufClear — mark the VRAM buffer empty for this frame.
; ----------------------------------------------------------------------------
.proc VBufClear
    lda #$00
    sta VBUF            ; hi = 0 => NMI flush does nothing
    rts
.endproc

; ----------------------------------------------------------------------------
; UpdateGame — top-level state machine for field walking vs. the text window.
; ----------------------------------------------------------------------------
.proc UpdateGame
    lda gamestate
    cmp #GS_OPENING
    beq @opening
    cmp #GS_DIALOG
    beq @dialog
    cmp #GS_CLOSING
    beq @closing
    cmp #GS_BATTLE
    beq @battle

    ; --- GS_FIELD ---
    jsr UpdateHero

    ; Interactions and encounters only resolve when the hero is grid-aligned.
    ldx #HERO
    lda ent_state,x
    cmp #ST_IDLE
    bne @ret

    ; Encounter trigger: debug button (Select) or the step counter.
    lda pad1_new
    and #BTN_SELECT
    bne @encounter
    lda step_count
    cmp #ENC_STEPS
    bcs @encounter

    ; Otherwise: talk to the NPC with A.
    lda pad1_new
    and #BTN_A
    beq @ret
    jsr FacingNPC       ; carry set if adjacent to and facing the NPC
    bcc @ret
    lda #0
    sta job_step
    lda #GS_OPENING
    sta gamestate
@ret:
    rts

@encounter:
    lda #0
    sta step_count
    jsr EnterBattle
    rts

@battle:
    ; Placeholder until Step 6 (stub battle + return).
    rts

@opening:
    lda #0              ; draw mode = opening
    sta draw_mode
    jsr DrawStep
    inc job_step
    lda job_step
    cmp #WIN_STEPS
    bcc @ret2
    lda #GS_DIALOG
    sta gamestate
@ret2:
    rts

@dialog:
    lda pad1_new
    and #BTN_A
    beq @ret3
    lda #0
    sta job_step
    lda #GS_CLOSING
    sta gamestate
@ret3:
    rts

@closing:
    lda #1              ; draw mode = closing (restore field)
    sta draw_mode
    jsr DrawStep
    inc job_step
    lda job_step
    cmp #WIN_STEPS
    bcc @ret4
    lda #GS_FIELD
    sta gamestate
@ret4:
    rts
.endproc

; FacingNPC — carry set if the cell the hero faces is the NPC's cell.
; X = HERO on entry.
.proc FacingNPC
    lda ent_gx,x
    sta newgx
    lda ent_gy,x
    sta newgy
    lda ent_dir,x
    cmp #DIR_UP
    bne @nu
    dec newgy
    jmp @cmp
@nu:
    cmp #DIR_DOWN
    bne @nd
    inc newgy
    jmp @cmp
@nd:
    cmp #DIR_LEFT
    bne @nl
    dec newgx
    jmp @cmp
@nl:
    inc newgx           ; DIR_RIGHT
@cmp:
    lda newgx
    cmp #NPC_GX
    bne @no
    lda newgy
    cmp #NPC_GY
    bne @no
    sec
    rts
@no:
    clc
    rts
.endproc

; DrawStep — build one VRAM packet for window step job_step. draw_mode selects
; the opening (window) or closing (field-restore) source table.
.proc DrawStep
    ldx job_step
    lda step_hi,x
    sta VBUF
    lda step_lo,x
    sta vpkt_lo
    lda step_cnt,x
    sta vpkt_cnt

    txa
    asl a
    tay                 ; Y = step * 2 (word index)
    lda draw_mode
    bne @close
    lda open_src,y
    sta ptr
    lda open_src+1,y
    sta ptr+1
    jmp @build
@close:
    lda close_src,y
    sta ptr
    lda close_src+1,y
    sta ptr+1
@build:
    ; emit packet header + data into VBUF (VBUF hi already set above)
    lda vpkt_lo
    sta VBUF+1
    lda vpkt_cnt
    sta VBUF+2
    ldy #0
@copy:
    lda (ptr),y
    sta VBUF+3,y
    iny
    cpy vpkt_cnt
    bne @copy
    rts
.endproc

; ----------------------------------------------------------------------------
; Window draw tables (9 steps: 8 tile chunks of 8 + 1 attribute write of 4).
; All target nametable 0 ($23xx) / its attribute table ($23F2).
; ----------------------------------------------------------------------------
.segment "RODATA"
step_hi:
    .byte $23, $23, $23, $23, $23, $23, $23, $23, $23
step_lo:
    .byte $08, $10, $28, $30, $48, $50, $68, $70, $F2
step_cnt:
    .byte 8, 8, 8, 8, 8, 8, 8, 8, 4

; opening: source the window tilemap, then the window attribute bytes
open_src:
    .word winmap+0,  winmap+8,  winmap+16, winmap+24
    .word winmap+32, winmap+40, winmap+48, winmap+56
    .word winattr

; closing: source the original field tiles under the window, then its attrs
close_src:
    .word fieldmap+776, fieldmap+784, fieldmap+808, fieldmap+816
    .word fieldmap+840, fieldmap+848, fieldmap+872, fieldmap+880
    .word fieldattr+50

winattr:
    .byte $FF, $FF, $FF, $FF   ; window region -> palette 3 in all quadrants

; ----------------------------------------------------------------------------
; LoadPalette — write 32 palette entries from (ptr). Rendering must be off.
; ----------------------------------------------------------------------------
.proc LoadPalette
    bit PPUSTATUS
    lda #$3F
    sta PPUADDR
    lda #$00
    sta PPUADDR
    ldy #$00
:   lda (ptr),y
    sta PPUDATA
    iny
    cpy #32
    bne :-
    rts
.endproc

; ----------------------------------------------------------------------------
; EnterBattle — cut from the field to the battle screen. Performed with NMI
; and rendering disabled (same safe window as boot), then both re-enabled.
; ----------------------------------------------------------------------------
.proc EnterBattle
    jsr WaitFrame       ; sync to the start of a frame
    lda #$00
    sta PPUCTRL         ; NMI off
    sta PPUMASK         ; rendering off -> VRAM is freely writable

    jsr DrawBattle
    lda #<pal_battle
    sta ptr
    lda #>pal_battle
    sta ptr+1
    jsr LoadPalette

    ; Hide the hero and push it to the PPU now, so it never appears on the
    ; battle screen when rendering resumes (next NMI's DMA would be too late).
    jsr HideHero
    lda #$00
    sta OAMADDR
    lda #>OAM_BUF
    sta OAMDMA

    bit PPUSTATUS       ; reset scroll before rendering resumes
    lda #$00
    sta PPUSCROLL
    sta PPUSCROLL

    lda #%10001000
    sta PPUCTRL         ; NMI on, sprite pattern table 1
    lda #%00011110
    sta PPUMASK         ; rendering on

    lda #GS_BATTLE
    sta gamestate
    rts
.endproc

; ----------------------------------------------------------------------------
; DrawBattle — fill nametable 0 with the blank tile (solid backdrop color from
; the battle palette). The enemy is added in Step 6. Rendering must be off.
; ----------------------------------------------------------------------------
.proc DrawBattle
    bit PPUSTATUS
    lda #$20
    sta PPUADDR
    lda #$00
    sta PPUADDR
    lda #$00
    ldx #$04            ; 4 x 256 = 1024 bytes (tiles + attributes)
    ldy #$00
:   sta PPUDATA
    iny
    bne :-
    dex
    bne :-
    rts
.endproc

; ----------------------------------------------------------------------------
; HideHero — park the hero's 4 metasprite entries off-screen (battle screen).
; ----------------------------------------------------------------------------
.proc HideHero
    lda #$FF
    sta oam+0
    sta oam+4
    sta oam+8
    sta oam+12
    rts
.endproc

; ----------------------------------------------------------------------------
; DrawField — copy the one-screen map (960 bytes) to nametable 0 ($2000) and
; the attribute table (64 bytes) to $23C0. Init-time only (rendering off).
; ----------------------------------------------------------------------------
.proc DrawField
    ; Nametable tiles: 960 bytes = 3 full pages + 192.
    bit PPUSTATUS
    lda #$20
    sta PPUADDR
    lda #$00
    sta PPUADDR

    lda #<fieldmap
    sta ptr
    lda #>fieldmap
    sta ptr+1

    ldx #$03            ; 3 full 256-byte pages
@page:
    ldy #$00
@byte:
    lda (ptr),y
    sta PPUDATA
    iny
    bne @byte
    inc ptr+1
    dex
    bne @page

    ldy #$00            ; remaining 192 bytes (ptr now at fieldmap+768)
@tail:
    lda (ptr),y
    sta PPUDATA
    iny
    cpy #192
    bne @tail

    ; Attribute table at $23C0: 64 bytes.
    lda #$23
    sta PPUADDR
    lda #$C0
    sta PPUADDR
    ldx #$00
@attr:
    lda fieldattr,x
    sta PPUDATA
    inx
    cpx #64
    bne @attr
    rts
.endproc

; ----------------------------------------------------------------------------
; Palette data. Only $3F00 (universal backdrop) is visible for the solid
; screen; the rest are seeded so later steps have sane defaults.
; ----------------------------------------------------------------------------
.segment "RODATA"
pal_field:
    ; Background palettes:
    .byte $0F, $1A, $2A, $07   ; 0: ground  - greens + brown (grass/tree/path/wall)
    .byte $0F, $0C, $11, $21   ; 1: water   - teal/blue/light blue
    .byte $0F, $11, $27, $30   ; 2: NPC     - blue robe, tan skin, white
    .byte $0F, $30, $0F, $16   ; 3: window  - white paper, black ink
    ; Sprite palettes (seeded for later steps):
    .byte $0F, $16, $27, $30
    .byte $0F, $0C, $11, $30
    .byte $0F, $1A, $2A, $30
    .byte $0F, $0F, $30, $0F

pal_battle:
    ; Battle backdrop = blue ($11), clearly distinct from the field. Tiles are
    ; blank for now (Step 6 adds the enemy); remaining entries seeded for it.
    .byte $11, $0F, $10, $30
    .byte $11, $0F, $10, $30
    .byte $11, $0F, $10, $30
    .byte $11, $0F, $10, $30
    .byte $0F, $16, $27, $30
    .byte $0F, $06, $16, $30
    .byte $0F, $0C, $1C, $30
    .byte $0F, $0F, $30, $0F

; ----------------------------------------------------------------------------
; Interrupt vectors
; ----------------------------------------------------------------------------
.segment "VECTORS"
    .word NMI
    .word RESET
    .word IRQ

; CHR-ROM tile data lives in chr.s (generated by tools/gen_assets.py).
