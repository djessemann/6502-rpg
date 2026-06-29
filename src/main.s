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
.include "tiles.inc"   ; generated tile-index constants (gen_assets.py)

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
GS_BATTLE  = 4          ; battle: enemy shown, waiting for an attack
GS_ENEMYDIE = 5         ; erasing the enemy tiles (one row per frame)
GS_BATTLEWAIT = 6       ; brief pause after the enemy vanishes, then return

; WIN_STEPS comes from tiles.inc (window draw chunks). Window is a full-width
; box at nametable rows 20-27; nametable base of row 20 = $2000 + 20*32 = $2280.
WIN_NT_HI  = $22
WIN_NT_LO  = $80        ; low byte of $2280

ENC_STEPS  = 16         ; grid steps before an encounter fires
DIE_DELAY  = 30         ; frames to wait after the enemy dies before returning

; Facing / movement directions
DIR_UP     = 0
DIR_DOWN   = 1
DIR_LEFT   = 2
DIR_RIGHT  = 3

; Entity states
ST_IDLE    = 0
ST_MOVE    = 1

MOVE_SPEED = 2          ; pixels/frame while sliding (16 / 2 = 8 frames per cell)

; Solid (impassable) field tiles. TILE_NPC_LO/HI come from tiles.inc.
TILE_TREE  = $04
TILE_WALL  = $05
TILE_WATER = $07

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
battle_timer: .res 1   ; countdown after the enemy dies
job_step:     .res 1   ; current window/enemy draw step
draw_mode:    .res 1   ; 0 = opening (draw window), 1 = closing (restore field)
vpkt_lo:      .res 1   ; packet being built: PPU address low / count
vpkt_cnt:     .res 1

; metasprite build scratch
sprbase:      .res 1   ; ent_dir * 4 (index into dir_tiles)
sprattr:      .res 1   ; OAM attribute byte for this facing
oamoff:       .res 1   ; current OAM slot offset (slot * 4)

woff:         .res 1   ; window draw: chunk index (k)
woff2:        .res 1   ; window draw: byte offset (k * 64)

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
    bcs @hide           ; any battle state (>= GS_BATTLE): no field sprites
    jsr BuildOAM        ; field/dialog: draw the hero metasprite
    jmp @sync
@hide:
    jsr HideHero
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
    cmp #TILE_NPC_LO    ; any NPC facing tile is solid
    bcc @walk
    cmp #TILE_NPC_HI + 1
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

; BuildOAM — write the hero's directional 4-tile metasprite into shadow OAM
; (entries 0-3). The tile set and flip are chosen by ent_dir: down/up use their
; own art; left/right share the side art, with left horizontally flipped (OAM
; attr bit 6) and its tile columns swapped. This is the reusable convention for
; every sprite character. OAM byte order: Y, tile, attr, X. Stored Y = screenY-1.
.proc BuildOAM
    ldx #HERO
    lda ent_dir,x
    asl a
    asl a
    sta sprbase         ; ent_dir * 4 = base index into dir_tiles
    ldy ent_dir,x
    lda dir_attr,y
    sta sprattr

    ldx #$00            ; slot 0..3 (TL, TR, BL, BR)
    lda #$00
    sta oamoff          ; slot * 4
@slot:
    ; Y (screen) = hero py + slot_dy - 1
    lda ent_py
    clc
    adc slot_dy,x
    sec
    sbc #1
    ldy oamoff
    sta oam,y

    ; tile = dir_tiles[sprbase + slot]
    txa
    clc
    adc sprbase
    tay
    lda dir_tiles,y
    ldy oamoff
    sta oam+1,y

    lda sprattr
    sta oam+2,y

    ; X (screen) = hero px + slot_dx
    lda ent_px
    clc
    adc slot_dx,x
    sta oam+3,y

    lda oamoff
    clc
    adc #4
    sta oamoff
    inx
    cpx #4
    bne @slot
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
    bne :+
    jmp @opening
:   cmp #GS_DIALOG
    bne :+
    jmp @dialog
:   cmp #GS_CLOSING
    bne :+
    jmp @closing
:   cmp #GS_BATTLE
    bne :+
    jmp @battle
:   cmp #GS_ENEMYDIE
    bne :+
    jmp @enemydie
:   cmp #GS_BATTLEWAIT
    bne :+
    jmp @battlewait
:

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
    ; Wait for the attack button.
    lda pad1_new
    and #BTN_A
    beq @ret
    lda #0
    sta job_step
    lda #GS_ENEMYDIE
    sta gamestate
    rts

@enemydie:
    ; Erase the enemy one tile-row per frame through the VRAM buffer.
    jsr EraseEnemyRow
    inc job_step
    lda job_step
    cmp #4
    bcc @ret
    lda #DIE_DELAY
    sta battle_timer
    lda #GS_BATTLEWAIT
    sta gamestate
    rts

@battlewait:
    dec battle_timer
    bne @ret
    jsr ExitBattle      ; cut back to the field at the prior position
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

; DrawStep — one VRAM packet for window draw step job_step (0..8). The window
; region (nametable rows 20-27) is 256 contiguous bytes at $2280. To avoid ever
; showing a tile under the wrong palette, transitions go through all-black:
;   steps 0-3 : clear the region to black tiles (64 each) -- still old palette
;   step  4   : set the region's 16 attribute bytes (new palette)
;   steps 5-8 : draw the real content (64 each) -- now palette matches
; Black (tile $00 = value 0) is palette-independent, so steps 0-4 never flash.
; draw_mode 0 = open (winmap / palette 3), 1 = close (field tiles / field attrs).
.proc DrawStep
    lda job_step
    cmp #4
    beq @attr
    bcs @content        ; 5-8
    sta woff            ; 0-3: clear, k = job_step
    jmp @tile
@content:
    sec
    sbc #5
    sta woff            ; 5-8: content, k = job_step - 5
@tile:
    ; byte offset = k * 64 ; dest = $2280 + offset
    lda woff
    asl a
    asl a
    asl a
    asl a
    asl a
    asl a
    sta woff2
    clc
    adc #WIN_NT_LO
    sta vpkt_lo
    lda #WIN_NT_HI
    adc #0
    sta VBUF
    lda #64
    sta vpkt_cnt

    lda job_step
    cmp #5
    bcc @clear_src      ; steps 0-3: black

    lda draw_mode
    bne @content_close
    lda #<winmap        ; open content: window tilemap
    clc
    adc woff2
    sta ptr
    lda #>winmap
    adc #0
    sta ptr+1
    jmp @build
@content_close:
    lda woff2           ; close content: fieldmap + 640 + offset
    clc
    adc #$80
    sta ptr
    lda #$02
    adc #0
    sta ptr+1
    lda ptr
    clc
    adc #<fieldmap
    sta ptr
    lda ptr+1
    adc #>fieldmap
    sta ptr+1
    jmp @build
@clear_src:
    lda #<win_zeros
    sta ptr
    lda #>win_zeros
    sta ptr+1
    jmp @build

@attr:
    ; 16 attribute bytes $23E8-$23F7 (rows 20-27, full width)
    lda #$23
    sta VBUF
    lda #$E8
    sta vpkt_lo
    lda #16
    sta vpkt_cnt
    lda draw_mode
    bne @attr_close
    lda #<winattr       ; open: palette 3 in all quadrants
    sta ptr
    lda #>winattr
    sta ptr+1
    jmp @build
@attr_close:
    lda #<(fieldattr + 40)   ; close: restore original attributes
    sta ptr
    lda #>(fieldattr + 40)
    sta ptr+1

@build:
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

.segment "RODATA"
winattr:
    .byte $FF, $FF, $FF, $FF, $FF, $FF, $FF, $FF   ; palette 3, all 16 quadrants
    .byte $FF, $FF, $FF, $FF, $FF, $FF, $FF, $FF
win_zeros:
    .res 64, $00                                    ; black-tile fill source

; Enemy: 4x4 background tiles at nametable cols 14-17, rows 12-15.
; Row low bytes: $2000 + (12+r)*32 + 14. Tiles are ENEMY_TILE_BASE..+15.
enemy_lo:
    .byte $8E, $AE, $CE, $EE

; Hero metasprite directional tables, indexed by ent_dir (UP,DOWN,LEFT,RIGHT).
; Each row lists the tiles for screen slots TL,TR,BL,BR. LEFT reuses the side
; (right-facing) art with columns swapped and the H-flip attribute set.
dir_tiles:
    .byte HERO_UP_TILE+0,   HERO_UP_TILE+1,   HERO_UP_TILE+2,   HERO_UP_TILE+3
    .byte HERO_DOWN_TILE+0, HERO_DOWN_TILE+1, HERO_DOWN_TILE+2, HERO_DOWN_TILE+3
    .byte HERO_SIDE_TILE+1, HERO_SIDE_TILE+0, HERO_SIDE_TILE+3, HERO_SIDE_TILE+2
    .byte HERO_SIDE_TILE+0, HERO_SIDE_TILE+1, HERO_SIDE_TILE+2, HERO_SIDE_TILE+3
dir_attr:
    .byte $00, $00, $40, $00   ; LEFT = horizontal flip
slot_dx:
    .byte 0, 8, 0, 8
slot_dy:
    .byte 0, 0, 8, 8

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
; DrawBattle — blank the nametable to the battle backdrop, then draw the enemy
; (4x4 background tiles, centered) and set its attribute to palette 1.
; Rendering must be off.
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

    ; Draw the enemy: 4 tile-rows of 4 sequential tiles from ENEMY_TILE_BASE.
    ldx #ENEMY_TILE_BASE   ; running tile id
    ldy #$00               ; row counter (0..3)
@row:
    bit PPUSTATUS
    lda #$21
    sta PPUADDR
    lda enemy_lo,y
    sta PPUADDR
    txa
    sta PPUDATA
    inx
    txa
    sta PPUDATA
    inx
    txa
    sta PPUDATA
    inx
    txa
    sta PPUDATA
    inx
    iny
    cpy #4
    bne @row

    ; Enemy attribute bytes 27 and 28 ($23DB-$23DC) -> palette 1.
    bit PPUSTATUS
    lda #$23
    sta PPUADDR
    lda #$DB
    sta PPUADDR
    lda #%01010101
    sta PPUDATA
    sta PPUDATA
    rts
.endproc

; ----------------------------------------------------------------------------
; ExitBattle — cut back to the field at the hero's prior position (its entity
; data was untouched during battle). Mirror of EnterBattle.
; ----------------------------------------------------------------------------
.proc ExitBattle
    jsr WaitFrame
    lda #$00
    sta PPUCTRL         ; NMI off
    sta PPUMASK         ; rendering off

    jsr DrawField
    lda #<pal_field
    sta ptr
    lda #>pal_field
    sta ptr+1
    jsr LoadPalette

    ; Rebuild the hero sprite and push it before rendering resumes.
    jsr BuildOAM
    lda #$00
    sta OAMADDR
    lda #>OAM_BUF
    sta OAMDMA

    bit PPUSTATUS
    lda #$00
    sta PPUSCROLL
    sta PPUSCROLL

    lda #%10001000
    sta PPUCTRL
    lda #%00011110
    sta PPUMASK

    lda #GS_FIELD
    sta gamestate
    rts
.endproc

; ----------------------------------------------------------------------------
; EraseEnemyRow — queue a VRAM packet blanking the 4 tiles of enemy row
; job_step (0..3), erasing the background-drawn enemy over four frames.
; ----------------------------------------------------------------------------
.proc EraseEnemyRow
    ldx job_step
    lda #$21
    sta VBUF            ; all enemy rows live in the $21xx nametable page
    lda enemy_lo,x
    sta VBUF+1
    lda #$04
    sta VBUF+2
    lda #$00
    sta VBUF+3
    sta VBUF+4
    sta VBUF+5
    sta VBUF+6
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
    ; NOTE: the first entry of each sprite-palette row ($3F10/$14/$18/$1C) must
    ; match the backdrop ($11) because those addresses mirror $3F00/$04/$08/$0C;
    ; writing $0F there would clobber the backdrop to black.
    .byte $11, $0F, $10, $30   ; 0: (unused on the blank screen)
    .byte $11, $13, $24, $30   ; 1: enemy - violet body, magenta shade, white
    .byte $11, $0F, $10, $30
    .byte $11, $0F, $10, $30
    .byte $11, $16, $27, $30
    .byte $11, $06, $16, $30
    .byte $11, $0C, $1C, $30
    .byte $11, $0F, $30, $0F

; ----------------------------------------------------------------------------
; Interrupt vectors
; ----------------------------------------------------------------------------
.segment "VECTORS"
    .word NMI
    .word RESET
    .word IRQ

; CHR-ROM tile data lives in chr.s (generated by tools/gen_assets.py).
