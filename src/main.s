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

.import fieldmap, fieldattr, ntmap_r, ntattr_r, worldsolid, winmap, msg_table
.import frag_DMG_PRE, frag_DMG_POST
.import frag_OPT_TALK, frag_OPT_EQUIP, frag_WPN0, frag_WPN1
.import frag_LBL_ATK, frag_LBL_POWER

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
GS_TEXT    = 7          ; rendering message lines into the open box
GS_TEXTWAIT = 8         ; page full ("more" prompt shown), waiting for A
GS_BWAIT   = 9          ; battle message shown, waiting for A to advance combat
GS_MENU    = 10         ; command/equip menu shown, handling cursor input

; message context: where GS_TEXT goes when a message ends
CTX_FIELD  = 0          ; -> GS_DIALOG (wait A, then close)
CTX_BATTLE = 1          ; -> GS_BWAIT (drive the battle)
CTX_MENU   = 2          ; -> GS_MENU (handle cursor input)

; menus
MENU_CMD   = 0          ; Talk / Equip
MENU_EQUIP = 1          ; weapon list
NUM_WEAPONS = 2

; battle phases (what the pending A press does)
BP_INTRO   = 0          ; intro shown; A -> first attack
BP_FIGHT   = 1          ; damage shown, enemy alive; A -> attack again
BP_DEAD    = 2          ; damage shown, enemy at 0; A -> defeat message
BP_DEFEATED = 3         ; defeat shown; A -> erase enemy and return

ENEMY_MAX_HP = 15

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

; WORLD_W / WORLD_H (metatile grid dimensions) come from tiles.inc.

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

; camera (NMI reads these to set the scroll position each frame)
camX_lo:      .res 1   ; horizontal scroll low 8 bits
camX_hi:      .res 1   ; horizontal scroll bit 8 -> PPUCTRL base-nametable bit0

; metasprite build scratch
sprbase:      .res 1   ; ent_dir * 4 (index into dir_tiles)
sprattr:      .res 1   ; OAM attribute byte for this facing
oamoff:       .res 1   ; current OAM slot offset (slot * 4)

woff:         .res 1   ; window draw: chunk index (k)
woff2:        .res 1   ; window draw: byte offset (k * 64)

; text engine
msg_ptr:      .res 2   ; pointer into the current message byte stream
dst:          .res 2   ; compose destination pointer
cur_line:     .res 1   ; interior line being rendered (0..TEXT_LINES-1)
term_action:  .res 1   ; how the last line ended: 0=newline 1=page 2=end
aux_flag:     .res 1   ; one-shot latch (e.g. "prompt drawn")
msg_context:  .res 1   ; CTX_FIELD / CTX_BATTLE
in_battle:    .res 1   ; nonzero while on the battle screen (hides the hero)

; battle / combat
enemy_hp:     .res 1
last_damage:  .res 1
battle_phase: .res 1
num:          .res 1   ; value AppendNumber renders

; menus / equipment
menu_id:      .res 1   ; MENU_CMD / MENU_EQUIP
menu_cursor:  .res 1   ; highlighted item (0..menu_max)
menu_max:     .res 1   ; last valid cursor index
equipped:     .res 1   ; equipped weapon index
player_atk:   .res 1   ; attack power of the equipped weapon

; ----------------------------------------------------------------------------
; Shadow OAM (DMA source page, $0200-$02FF)
; ----------------------------------------------------------------------------
.segment "OAMBUF"
oam:          .res 256

; ----------------------------------------------------------------------------
; Entities — struct-of-arrays, indexed by entity number (X register).
; ----------------------------------------------------------------------------
.segment "BSS"
ent_gx:    .res MAX_ENT   ; grid cell X (16px cells, 0..WORLD_W-1)
ent_gy:    .res MAX_ENT   ; grid cell Y (0..WORLD_H-1)
ent_px:    .res MAX_ENT   ; world pixel X, low byte (top-left)
ent_pxh:   .res MAX_ENT   ; world pixel X, high bit (world is 512px wide)
ent_py:    .res MAX_ENT   ; world pixel Y (top-left)
ent_dir:   .res MAX_ENT   ; facing direction
ent_state: .res MAX_ENT   ; ST_IDLE / ST_MOVE
ent_timer: .res MAX_ENT   ; pixels remaining in the current slide

msg_buf:   .res 40        ; runtime-composed message (e.g. damage line)

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
    jsr UpdateCamera    ; recompute scroll from the hero's world position
    ; The hero is on screen everywhere except the battle screen.
    lda in_battle
    bne @hide
    jsr BuildOAM
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

    ; Set scroll after any potential $2006 write this frame. The camera's
    ; high bit selects which nametable is top-left (horizontal scroll spans the
    ; two side-by-side screens). Vertical scroll is fixed at 0 (world is 1 tall).
    bit PPUSTATUS
    lda camX_lo
    sta PPUSCROLL
    lda #$00
    sta PPUSCROLL
    lda #%10001000
    ora camX_hi
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
    sta ent_gx,x        ; start on open grass, left screen
    lda #9
    sta ent_gy,x
    lda #4 * 16
    sta ent_px,x        ; world pixel position = cell * 16
    lda #0
    sta ent_pxh,x       ; left screen -> high bit clear
    lda #9 * 16
    sta ent_py,x
    lda #DIR_DOWN
    sta ent_dir,x
    lda #ST_IDLE
    sta ent_state,x

    jsr UpdateCamera    ; seed the camera before the first frame

    lda #0              ; start equipped with weapon 0 (Club)
    sta equipped
    lda weapon_atk
    sta player_atk

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

; Attempt to start a step in ent_dir,x. The target cell wraps around the edges
; (16 cols x 15 rows), so there is no border; only solid tiles block. Enters the
; sliding state on success (the cell is committed when the slide finishes).
; X = entity index.
.proc TryStep
    lda ent_gx,x
    sta newgx
    lda ent_gy,x
    sta newgy

    lda ent_dir,x
    cmp #DIR_UP
    bne @nu
    lda newgy           ; up: gy-1, wrap 0 -> WORLD_H-1
    bne @up_dec
    lda #WORLD_H - 1
    sta newgy
    jmp @check
@up_dec:
    dec newgy
    jmp @check
@nu:
    cmp #DIR_DOWN
    bne @nd
    lda newgy           ; down: gy+1, wrap WORLD_H-1 -> 0
    cmp #WORLD_H - 1
    bcc @dn_inc
    lda #0
    sta newgy
    jmp @check
@dn_inc:
    inc newgy
    jmp @check
@nd:
    cmp #DIR_LEFT
    bne @nl
    lda newgx           ; left: gx-1, wrap 0 -> WORLD_W-1
    bne @lf_dec
    lda #WORLD_W - 1
    sta newgx
    jmp @check
@lf_dec:
    dec newgx
    jmp @check
@nl:
    lda newgx           ; right: gx+1, wrap WORLD_W-1 -> 0
    cmp #WORLD_W - 1
    bcc @rt_inc
    lda #0
    sta newgx
    jmp @check
@rt_inc:
    inc newgx

@check:
    lda newgx
    sta cs_gx
    lda newgy
    sta cs_gy
    jsr CellSolid       ; carry set => solid
    bcs @blocked

    lda #ST_MOVE        ; begin the slide; cell is set when it completes
    sta ent_state,x
    lda #16
    sta ent_timer,x
@blocked:
    rts
.endproc

; Slide the hero MOVE_SPEED pixels in ent_dir. World position is canonical and
; wraps: X is 16-bit (mod 512 = two-screen world width), Y is 8-bit (mod 240 =
; world height). When 16px have been covered, snap the grid cell from the world
; position. X = entity index.
.proc StepMove
    lda ent_dir,x
    cmp #DIR_LEFT
    bne @nl
    lda ent_px,x        ; left: 16-bit subtract, wrap below 0 -> 510
    sec
    sbc #MOVE_SPEED
    sta ent_px,x
    lda ent_pxh,x
    sbc #0
    sta ent_pxh,x
    bpl @tick           ; >= 0 (high bit clear) -> fine
    clc
    adc #2              ; underflowed ($FF -> $01): + 512
    sta ent_pxh,x
    jmp @tick
@nl:
    cmp #DIR_RIGHT
    bne @nu
    lda ent_px,x        ; right: 16-bit add, wrap at 512 -> 0
    clc
    adc #MOVE_SPEED
    sta ent_px,x
    lda ent_pxh,x
    adc #0
    sta ent_pxh,x
    cmp #2              ; reached 512 (high byte = 2)?
    bcc @tick
    lda #0
    sta ent_pxh,x       ; wrap to world X = 0
    jmp @tick
@nu:
    cmp #DIR_UP
    bne @down
    lda ent_py,x        ; up: subtract, wrap mod 240
    sec
    sbc #MOVE_SPEED
    sta ent_py,x
    cmp #240
    bcc @tick
    sec
    sbc #16             ; underflow: convert byte-mod-256 to mod-240
    sta ent_py,x
    jmp @tick
@down:
    lda ent_py,x        ; down: add, wrap mod 240
    clc
    adc #MOVE_SPEED
    sta ent_py,x
    cmp #240
    bcc @tick
    sec
    sbc #240
    sta ent_py,x

@tick:
    lda ent_timer,x
    sec
    sbc #MOVE_SPEED
    sta ent_timer,x
    bne @done
    ; aligned again: gx = worldX / 16 = (pxh*16) | (px >> 4)
    lda ent_pxh,x
    asl a
    asl a
    asl a
    asl a
    sta ent_gx,x        ; pxh * 16 (0 or 16)
    lda ent_px,x
    lsr a
    lsr a
    lsr a
    lsr a
    ora ent_gx,x
    sta ent_gx,x
    lda ent_py,x        ; gy = worldY / 16
    lsr a
    lsr a
    lsr a
    lsr a
    sta ent_gy,x
    lda #ST_IDLE
    sta ent_state,x
    inc step_count
@done:
    rts
.endproc

; CellSolid — is the metatile cell (cs_gx,cs_gy) blocked? One grid cell is one
; 16px metatile, so this is a single lookup in worldsolid[cs_gy*WORLD_W+cs_gx]
; (1 = solid). Returns carry set if solid. Preserves X.
.proc CellSolid
    lda #0
    sta ptr+1
    lda cs_gy           ; cs_gy * 32 (WORLD_W) -> ptr+1:A
    asl a
    rol ptr+1
    asl a
    rol ptr+1
    asl a
    rol ptr+1
    asl a
    rol ptr+1
    asl a
    rol ptr+1
    clc
    adc cs_gx
    bcc :+
    inc ptr+1
:   clc
    adc #<worldsolid
    sta ptr
    lda ptr+1
    adc #>worldsolid
    sta ptr+1
    ldy #0
    lda (ptr),y
    beq @clear
    sec                 ; nonzero -> solid
    rts
@clear:
    clc
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
    ; Y (screen) = (py + slot_dy) wrapped at the bottom seam (240), then - 1
    lda ent_py
    clc
    adc slot_dy,x
    cmp #240
    bcc :+
    sec
    sbc #240
:   sec
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

    ; X (screen) = 128 + slot_dx. The camera keeps the hero centered, so its
    ; screen X is fixed and the world scrolls under it (Dragon-Quest style).
    lda #128
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
; UpdateCamera — center the camera on the hero: camX = heroWorldX - 128, taken
; mod 512 (the world wraps). The 9-bit result is split into camX_lo (low 8 bits,
; the PPUSCROLL value) and camX_hi (bit 8, the base-nametable select). With the
; hero held at screen X = 128, the world scrolls smoothly beneath it.
; ----------------------------------------------------------------------------
.proc UpdateCamera
    ldx #HERO
    lda ent_px,x
    sec
    sbc #128
    sta camX_lo
    lda ent_pxh,x
    sbc #0
    and #$01            ; mod 512: keep only bit 8 (handles the borrow case)
    sta camX_hi
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
:   cmp #GS_BWAIT
    bne :+
    jmp @bwait
:   cmp #GS_ENEMYDIE
    bne :+
    jmp @enemydie
:   cmp #GS_BATTLEWAIT
    bne :+
    jmp @battlewait
:   cmp #GS_TEXT
    bne :+
    jmp @text
:   cmp #GS_TEXTWAIT
    bne :+
    jmp @textwait
:   cmp #GS_MENU
    bne :+
    jmp @menu
:

    ; --- GS_FIELD ---
    ; Milestone 1 (scrolling overworld): walking only. The A-menu and encounter
    ; triggers are gated until the text box is made camera-aware; their handlers
    ; (@encounter, @bwait, @menu, ...) remain below for that re-integration.
    jsr UpdateHero
@ret:
    rts

@encounter:
    lda #0
    sta step_count
    jsr EnterBattle
    rts

@bwait:
    ; A battle message is on screen; A advances combat per battle_phase.
    lda pad1_new
    and #BTN_A
    beq @ret
    lda battle_phase
    cmp #BP_DEFEATED
    beq @bw_done
    cmp #BP_DEAD
    beq @bw_defeat
    ; BP_INTRO or BP_FIGHT -> attack
    jsr DoAttack            ; sets last_damage, decrements enemy_hp, composes msg
    lda #<msg_buf
    sta msg_ptr
    lda #>msg_buf
    sta msg_ptr+1
    lda enemy_hp
    bne @bw_alive
    lda #BP_DEAD
    sta battle_phase
    jmp @bw_show
@bw_alive:
    lda #BP_FIGHT
    sta battle_phase
@bw_show:
    lda #0
    sta cur_line
    lda #GS_TEXT
    sta gamestate
    rts
@bw_defeat:
    lda #MSG_SLIME_DEFEATED
    jsr SetMessage
    lda #BP_DEFEATED
    sta battle_phase
    lda #0
    sta cur_line
    lda #GS_TEXT
    sta gamestate
    rts
@bw_done:
    lda #0
    sta job_step
    lda #GS_ENEMYDIE        ; erase the enemy, then ExitBattle
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
    lda #0              ; box is open: start rendering text
    sta cur_line
    lda #GS_TEXT
    sta gamestate
@ret2:
    rts

@text:
    jsr RenderLine      ; one interior line into the VRAM buffer this frame
    inc cur_line
    lda term_action
    beq @ret3           ; 0 = newline: keep rendering
    cmp #1
    bne @text_end       ; 2 = end of message
    lda #0              ; 1 = page break: show the prompt and wait
    sta aux_flag
    lda #GS_TEXTWAIT
    sta gamestate
    rts
@text_end:
    lda msg_context
    cmp #CTX_BATTLE
    bne @te_notbattle
    lda #GS_BWAIT       ; battle: wait for A to drive combat
    sta gamestate
    rts
@te_notbattle:
    cmp #CTX_MENU
    bne @text_field
    lda #GS_MENU        ; menu: handle cursor input
    sta gamestate
    rts
@text_field:
    lda #GS_DIALOG      ; field: wait for A, then close
    sta gamestate
@ret3:
    rts

@textwait:
    lda aux_flag        ; draw the "more" prompt once, then poll A
    bne @tw_poll
    jsr DrawPrompt
    lda #1
    sta aux_flag
    rts
@tw_poll:
    lda pad1_new
    and #BTN_A
    beq @ret5
    jsr ErasePrompt
    lda #0
    sta cur_line
    lda #GS_TEXT
    sta gamestate
@ret5:
    rts

@dialog:
    lda pad1_new
    and #BTN_A
    beq @ret4
    lda #0
    sta job_step
    lda #GS_CLOSING
    sta gamestate
@ret4:
    rts

@menu:
    lda pad1_new
    and #BTN_UP
    beq @m_notup
    lda menu_cursor
    bne @m_up_ok
    rts                 ; already at top
@m_up_ok:
    dec menu_cursor
    jsr RenderMenu
    rts
@m_notup:
    lda pad1_new
    and #BTN_DOWN
    beq @m_notdown
    lda menu_cursor
    cmp menu_max
    bcc @m_down_ok
    rts                 ; already at bottom
@m_down_ok:
    inc menu_cursor
    jsr RenderMenu
    rts
@m_notdown:
    lda pad1_new
    and #BTN_B
    bne @m_cancel
    lda pad1_new
    and #BTN_A
    beq @m_done
    ; --- A: confirm the highlighted item ---
    lda menu_id
    cmp #MENU_EQUIP
    beq @m_equip
    ; command menu
    lda menu_cursor
    bne @m_open_equip   ; cursor 1 = Equip
    ; cursor 0 = Talk
    ldx #HERO
    jsr FacingNPC
    bcc @m_nobody
    lda #MSG_NPC_GREETING
    jmp @m_field_msg
@m_nobody:
    lda #MSG_NOBODY
@m_field_msg:
    pha
    lda #CTX_FIELD
    sta msg_context
    pla
    jsr SetMessage
    lda #0
    sta cur_line
    lda #GS_TEXT
    sta gamestate
    rts
@m_open_equip:
    lda #MENU_EQUIP
    sta menu_id
    lda equipped
    sta menu_cursor
    lda #1
    sta menu_max
    jsr RenderMenu
    rts
@m_equip:
    lda menu_cursor     ; equip the highlighted weapon
    sta equipped
    tax
    lda weapon_atk,x
    sta player_atk
    jsr RenderMenu      ; re-render so "Power" updates
    rts
@m_cancel:
    lda menu_id
    cmp #MENU_EQUIP
    bne @m_close
    lda #MENU_CMD       ; equip -> back to command menu
    sta menu_id
    lda #1
    sta menu_cursor
    lda #1
    sta menu_max
    jsr RenderMenu
    rts
@m_close:
    lda #0              ; command menu -> close the box
    sta job_step
    lda #GS_CLOSING
    sta gamestate
@m_done:
    rts

@closing:
    lda #1              ; draw mode = closing (restore field)
    sta draw_mode
    jsr DrawStep
    inc job_step
    lda job_step
    cmp #WIN_STEPS
    bcc @ret6
    lda #GS_FIELD
    sta gamestate
@ret6:
    rts
.endproc

; SetMessage — point msg_ptr at message id A (index into msg_table).
.proc SetMessage
    asl a
    tay
    lda msg_table,y
    sta msg_ptr
    lda msg_table+1,y
    sta msg_ptr+1
    rts
.endproc

; DoAttack — deal the equipped weapon's attack power to the enemy (capped to
; remaining HP) and compose the "takes N damage" line.
.proc DoAttack
    lda player_atk
    cmp enemy_hp
    bcc :+
    lda enemy_hp        ; never report more than what's left
:   sta last_damage
    lda enemy_hp
    sec
    sbc last_damage
    sta enemy_hp
    ; fall through to compose the message
.endproc

; ComposeDamage — build "<DMG_PRE><last_damage><DMG_POST>" + 3 blank lines + end
; into msg_buf, ready for RenderLine.
.proc ComposeDamage
    lda #<msg_buf
    sta dst
    lda #>msg_buf
    sta dst+1
    lda #<frag_DMG_PRE
    sta ptr
    lda #>frag_DMG_PRE
    sta ptr+1
    jsr CopyFrag
    lda last_damage
    sta num
    jsr AppendNumber
    lda #<frag_DMG_POST
    sta ptr
    lda #>frag_DMG_POST
    sta ptr+1
    jsr CopyFrag
    lda #MSG_NEWLINE
    jsr StoreDst
    lda #MSG_NEWLINE
    jsr StoreDst
    lda #MSG_NEWLINE
    jsr StoreDst
    lda #MSG_END
    jsr StoreDst
    rts
.endproc

; CopyFrag — append the $FF-terminated tile stream at (ptr) to (dst).
.proc CopyFrag
@l:
    ldy #0
    lda (ptr),y
    cmp #$FF
    beq @done
    jsr StoreDst
    inc ptr
    bne @l
    inc ptr+1
    jmp @l
@done:
    rts
.endproc

; AppendNumber — append `num` as 1-2 decimal digit tiles to (dst).
.proc AppendNumber
    lda num
    ldx #$FF
@div:
    inx
    sec
    sbc #10
    bcs @div
    adc #10             ; A = ones, X = tens
    pha                 ; save ones
    txa
    beq @ones           ; no tens digit
    clc
    adc #DIGIT_TILE
    jsr StoreDst
@ones:
    pla
    clc
    adc #DIGIT_TILE
    jsr StoreDst
    rts
.endproc

; StoreDst — store A at (dst) and advance dst.
.proc StoreDst
    ldy #0
    sta (dst),y
    inc dst
    bne :+
    inc dst+1
:   rts
.endproc

; OpenMenuBox — set up menu A and open the box (used from the field).
.proc OpenMenuBox
    sta menu_id
    lda #0
    sta menu_cursor
    lda #1
    sta menu_max
    lda #CTX_MENU
    sta msg_context
    jsr ComposeMenu
    lda #<msg_buf
    sta msg_ptr
    lda #>msg_buf
    sta msg_ptr+1
    lda #0
    sta job_step
    lda #GS_OPENING
    sta gamestate
    rts
.endproc

; RenderMenu — recompose the current menu and redraw it (box already open).
.proc RenderMenu
    jsr ComposeMenu
    lda #<msg_buf
    sta msg_ptr
    lda #>msg_buf
    sta msg_ptr+1
    lda #0
    sta cur_line
    lda #GS_TEXT
    sta gamestate
    rts
.endproc

; ComposeMenu — build the current menu (menu_id) into msg_buf: option lines with
; a cursor on menu_cursor, padded to 4 lines.
.proc ComposeMenu
    lda #<msg_buf
    sta dst
    lda #>msg_buf
    sta dst+1
    lda menu_id
    cmp #MENU_EQUIP
    beq @equip

    ; command menu: Talk / Equip
    ldx #0
    jsr EmitCursor
    lda #<frag_OPT_TALK
    sta ptr
    lda #>frag_OPT_TALK
    sta ptr+1
    jsr CopyFrag
    lda #MSG_NEWLINE
    jsr StoreDst
    ldx #1
    jsr EmitCursor
    lda #<frag_OPT_EQUIP
    sta ptr
    lda #>frag_OPT_EQUIP
    sta ptr+1
    jsr CopyFrag
    lda #MSG_NEWLINE
    jsr StoreDst
    lda #MSG_NEWLINE     ; line 2 blank
    jsr StoreDst
    lda #MSG_END         ; line 3 blank + end
    jsr StoreDst
    rts

@equip:
    ; weapon 0
    ldx #0
    jsr EmitCursor
    lda #<frag_WPN0
    sta ptr
    lda #>frag_WPN0
    sta ptr+1
    jsr CopyFrag
    jsr EmitAtk         ; " ATK " + weapon_atk[0]
    ldx #0
    lda weapon_atk,x
    sta num
    jsr AppendNumber
    lda #MSG_NEWLINE
    jsr StoreDst
    ; weapon 1
    ldx #1
    jsr EmitCursor
    lda #<frag_WPN1
    sta ptr
    lda #>frag_WPN1
    sta ptr+1
    jsr CopyFrag
    jsr EmitAtk
    ldx #1
    lda weapon_atk,x
    sta num
    jsr AppendNumber
    lda #MSG_NEWLINE
    jsr StoreDst
    lda #MSG_NEWLINE     ; line 2 blank
    jsr StoreDst
    ; line 3: "Power: N"
    lda #<frag_LBL_POWER
    sta ptr
    lda #>frag_LBL_POWER
    sta ptr+1
    jsr CopyFrag
    lda player_atk
    sta num
    jsr AppendNumber
    lda #MSG_END
    jsr StoreDst
    rts
.endproc

; EmitCursor — emit the cursor tile (if menu_cursor == X) or a blank, then a
; space, to (dst). Preserves nothing.
.proc EmitCursor
    cpx menu_cursor
    bne @blank
    lda #CURSOR_TILE
    jmp @put
@blank:
    lda #$00
@put:
    jsr StoreDst
    lda #$00            ; space after the cursor column
    jsr StoreDst
    rts
.endproc

; EmitAtk — append the " ATK " label fragment to (dst).
.proc EmitAtk
    lda #<frag_LBL_ATK
    sta ptr
    lda #>frag_LBL_ATK
    sta ptr+1
    jmp CopyFrag        ; tail call (rts from CopyFrag)
.endproc

.segment "RODATA"
weapon_atk:
    .byte 4, 8          ; Club, Sword

; RenderLine — render one interior line (cur_line) of the current message into
; the VRAM buffer, padding to TEXT_COLS. Sets term_action from the control code
; that ended the line: 0 = newline, 1 = page break, 2 = end of message.
; Interior line L is nametable row 22+L, cols 1-30 -> address $22C1 + L*32.
.proc RenderLine
    lda cur_line
    asl a
    asl a
    asl a
    asl a
    asl a
    clc
    adc #$C1
    sta vpkt_lo
    lda #$22
    adc #0
    sta VBUF
    lda #TEXT_COLS
    sta vpkt_cnt

    ldx #0              ; column / VBUF data index
    ldy #0
@read:
    lda (msg_ptr),y
    inc msg_ptr
    bne :+
    inc msg_ptr+1
:
    cmp #MSG_NEWLINE
    beq @nl
    cmp #MSG_PAGE
    beq @page
    cmp #MSG_END
    beq @end
    cpx #TEXT_COLS      ; overflow safety: discard but keep consuming
    bcs @read
    sta VBUF+3,x
    inx
    jmp @read
@nl:
    lda #0
    sta term_action
    jmp @pad
@page:
    lda #1
    sta term_action
    jmp @pad
@end:
    lda #2
    sta term_action
@pad:
    lda #$00
@padloop:
    cpx #TEXT_COLS
    bcs @done
    sta VBUF+3,x
    inx
    jmp @padloop
@done:
    lda vpkt_lo
    sta VBUF+1
    lda vpkt_cnt
    sta VBUF+2
    rts
.endproc

; DrawPrompt / ErasePrompt — the "more text" triangle on the bottom border,
; centered at nametable $236F (row 27, col 15).
.proc DrawPrompt
    lda #$23
    sta VBUF
    lda #$6F
    sta VBUF+1
    lda #1
    sta VBUF+2
    lda #ARROW_TILE
    sta VBUF+3
    rts
.endproc

.proc ErasePrompt
    lda #$23
    sta VBUF
    lda #$6F
    sta VBUF+1
    lda #1
    sta VBUF+2
    lda #WIN_BOTTOM_TILE
    sta VBUF+3
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

    ; Begin combat: set up state, then open the message box and show the intro.
    lda #1
    sta in_battle
    lda #ENEMY_MAX_HP
    sta enemy_hp
    lda #BP_INTRO
    sta battle_phase
    lda #CTX_BATTLE
    sta msg_context
    lda #MSG_SLIME_APPEARS
    jsr SetMessage
    lda #0
    sta job_step
    lda #GS_OPENING     ; open the box; GS_OPENING -> GS_TEXT renders the intro
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

    lda #$00
    sta in_battle
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
; DrawField — paint the whole two-screen world: the left screen to nametable 0
; ($2000, attrs $23C0) and the right screen to nametable 1 ($2400, attrs $27C0).
; Init-time / full-redraw only (rendering off).
; ----------------------------------------------------------------------------
.proc DrawField
    ; Left screen tiles -> $2000.
    bit PPUSTATUS
    lda #$20
    sta PPUADDR
    lda #$00
    sta PPUADDR
    lda #<fieldmap
    sta ptr
    lda #>fieldmap
    sta ptr+1
    jsr BlitScreen

    ; Left attributes -> $23C0.
    lda #$23
    sta PPUADDR
    lda #$C0
    sta PPUADDR
    ldx #$00
@al:
    lda fieldattr,x
    sta PPUDATA
    inx
    cpx #64
    bne @al

    ; Right screen tiles -> $2400.
    lda #$24
    sta PPUADDR
    lda #$00
    sta PPUADDR
    lda #<ntmap_r
    sta ptr
    lda #>ntmap_r
    sta ptr+1
    jsr BlitScreen

    ; Right attributes -> $27C0.
    lda #$27
    sta PPUADDR
    lda #$C0
    sta PPUADDR
    ldx #$00
@ar:
    lda ntattr_r,x
    sta PPUDATA
    inx
    cpx #64
    bne @ar
    rts
.endproc

; BlitScreen — copy 960 nametable bytes from (ptr) to PPUDATA (PPUADDR preset).
; 960 = 3 full 256-byte pages + 192. Clobbers ptr, X, Y, A.
.proc BlitScreen
    ldx #$03
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
    ldy #$00            ; remaining 192 bytes (ptr now at base+768)
@tail:
    lda (ptr),y
    sta PPUDATA
    iny
    cpy #192
    bne @tail
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
    ; Battle backdrop = black ($0F): the classic JRPG arena, and the color the
    ; text box needs (the box's black is value 0 = the backdrop). Every color-0
    ; entry is $0F so the $3F1x->$3F0x mirror can't clobber the backdrop.
    .byte $0F, $0F, $10, $30   ; 0: blank screen
    .byte $0F, $13, $24, $30   ; 1: enemy - violet body, magenta shade, white
    .byte $0F, $0F, $10, $30
    .byte $0F, $30, $0F, $16   ; 3: window - black paper, white ink
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
