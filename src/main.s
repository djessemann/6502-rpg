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

.import worldtiles, attr_pair_l, attr_pair_r, worldsolid, winmap, msg_table
.import frag_DMG_PRE, frag_DMG_POST
.import frag_OPT_TALK, frag_OPT_EQUIP, frag_WPN0, frag_WPN1
.import frag_LBL_ATK, frag_LBL_POWER, frag_LBL_HP
.import frag_OPT_FIGHT, frag_OPT_RUN, frag_EATK_PRE, frag_EATK_POST

; ----------------------------------------------------------------------------
; Constants
; ----------------------------------------------------------------------------
MAX_ENT    = 8          ; entity array length
HERO       = 0          ; entity index of the hero
CAT        = 1          ; entity index of the wandering cat NPC

; The cat wanders inside a home box (like a DQ townsperson), near spawn.
CAT_MIN_GX = 5
CAT_MAX_GX = 14
CAT_MIN_GY = 8
CAT_MAX_GY = 14
CAT_START_GX = 10
CAT_START_GY = 9

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
                        ; (4 is retired; battle runs through OPENING/TEXT/BWAIT)
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
MENU_BATTLE = 2         ; Fight / Run
NUM_WEAPONS = 2

; battle phases. The battle loop is: intro -> command menu -> (Fight: player
; damage message -> enemy counterattack message -> menu again) until one side
; drops, or (Run: flee message -> back to the field).
BP_INTRO   = 0          ; intro showing; when it ends -> command menu
BP_MENU    = 1          ; message shown, enemy alive; A -> command menu
BP_ENEMYTURN = 2        ; player damage shown, enemy alive; A -> enemy attacks
BP_DEAD    = 3          ; player damage shown, enemy at 0; A -> defeat message
BP_DEFEATED = 4         ; defeat shown; A -> erase enemy and return
BP_FLED    = 5          ; flee message shown; A -> back to the field
BP_DYING   = 6          ; enemy hit shown, hero at 0 HP; A -> death message
BP_PLAYERDEAD = 7       ; death message shown; A -> revive and return

ENEMY_MAX_HP = 15
PLAYER_MAX_HP = 24

; WIN_STEPS comes from tiles.inc (box draw chunks: 4 clear + 1 attr + 4 content).
; The box is a full-width, 8-row window at screen rows 20-27, drawn in place over
; the scrolled map (see ComputeBoxGeom / DrawStep).

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
cam_y_lo:     .res 1   ; vertical camera position 0..479 (16-bit)
cam_y_hi:     .res 1
scrollY:      .res 1   ; PPU vertical scroll for this frame (cam_y mod 240)
cam_ty:       .res 1   ; camera top tile-row (cam_y / 8, 0..59)
prev_cam_ty:  .res 1   ; previous frame's cam_ty (to detect 8px crossings)
stream_row:   .res 1   ; world TILE-row a crossing needs streamed in (0..59)
stream_req:   .res 1   ; number of queued stream strips for NMI (0 = none)
sd_idx:       .res 1   ; scratch: descriptor index while building/flushing
scnt:         .res 1   ; NMI scratch: current strip byte count
; row-stream build scratch (main thread)
rb_lo:        .res 1   ; nametable row base (nmr * 64), 16-bit
rb_hi:        .res 1
ms_lo:        .res 1   ; worldtiles source offset (MY * 128 + base), 16-bit
ms_hi:        .res 1
bs_par:       .res 1   ; scratch (MY / parity)
bs_cnt:       .res 1   ; scratch loop counter

; --- text-box geometry (the box is drawn in place over the scrolled map) ---
; Computed when a box opens; the box is 8 nametable rows, full screen width.
box_nt_base:  .res 1   ; nametable tile-row of the box top (0..29)
box_wrow:     .res 1   ; world tile-row of the box top (0..59), for the restore
box_cstart:   .res 1   ; nametable column of the box left edge (0..63)
bx_phase:     .res 1   ; DrawStep phase: 0 clear, 1 shell, 2 restore (map)
attr_force:   .res 1   ; MergeAttrRow: nonzero = force palette 3 (box) into shadow
nt_row_tmp:   .res 1   ; current nametable row being queued
; SplitRange outputs: a screen-relative run split across the two nametables
sr_cnt:       .res 1   ; input: tile count
sg1_base:     .res 1   ; segment 1 nametable base hi ($20/$24)
sg1_col:      .res 1   ; segment 1 start column
sg1_cnt:      .res 1   ; segment 1 tile count
sg2_base:     .res 1   ; segment 2 nametable base hi (other screen)
sg2_cnt:      .res 1   ; segment 2 tile count (0 = no split)

; metasprite build scratch
sprbase:      .res 1   ; ent_dir * 4 (index into dir_tiles)
sprattr:      .res 1   ; OAM attribute byte for this facing
sprfrm:       .res 1   ; walk-cycle tile offset (0 or HERO_FRAME_OFF)
rng:          .res 1   ; 8-bit LFSR for NPC wandering
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
box_open:     .res 1   ; nonzero while a field box is open (freezes streaming)

; battle / combat
enemy_hp:     .res 1
player_hp:    .res 1
last_damage:  .res 1
battle_phase: .res 1
hp_dirty:     .res 1   ; status window needs a redraw (flushed in GS_BWAIT)
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
ent_py:    .res MAX_ENT   ; world pixel Y, low byte (top-left)
ent_pyh:   .res MAX_ENT   ; world pixel Y, high bit (world is 480px tall)
ent_dir:   .res MAX_ENT   ; facing direction
ent_state: .res MAX_ENT   ; ST_IDLE / ST_MOVE
ent_timer: .res MAX_ENT   ; pixels remaining in the current slide

msg_buf:   .res 40        ; runtime-composed message (e.g. damage line)
linebuf:   .res 32        ; one rendered text line (before seam-split to VRAM)

; Attribute-table shadows (RAM copies of the two nametables' attributes). The
; row streamer read-modify-writes these (one metatile == one attr quadrant, so
; an attr byte mixes two metatile rows) and copies the touched bytes to VRAM.
attr_shadow_l: .res 64
attr_shadow_r: .res 64

; Row-stream descriptors: up to 6 strips per crossing (4 tile + 2 attribute),
; filled by the main thread, written to VRAM by the NMI. Parallel arrays.
STREAM_MAX = 6
sd_dst_hi: .res STREAM_MAX  ; PPU dest address high
sd_dst_lo: .res STREAM_MAX  ; PPU dest address low
sd_cnt:    .res STREAM_MAX  ; byte count
sd_src_lo: .res STREAM_MAX  ; source pointer low
sd_src_hi: .res STREAM_MAX  ; source pointer high

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
    jsr InitGame        ; place the hero + seed the camera (cam_ty) first
    jsr DrawField       ; ...so DrawField paints the world at the start camera

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
    jsr StreamRows      ; queue an incoming metatile row on a vertical crossing
    ; The hero is on screen everywhere except the battle screen.
    lda in_battle
    bne @hide
    jsr BuildOAM
    jsr BuildCatOAM
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

    ; Row streaming: write the incoming metatile-row's strips (queued by the
    ; main thread on a vertical crossing). Each descriptor is a contiguous run
    ; copied from a source pointer (PRG worldtiles, or the RAM attr shadow).
    lda stream_req
    beq @nostream
    sta sd_idx
@strip:
    ldx sd_idx
    dex
    bit PPUSTATUS
    lda sd_dst_hi,x
    sta PPUADDR
    lda sd_dst_lo,x
    sta PPUADDR
    lda sd_src_lo,x
    sta ptr
    lda sd_src_hi,x
    sta ptr+1
    lda sd_cnt,x
    sta scnt
    ldy #0
@scopy:
    lda (ptr),y
    sta PPUDATA
    iny
    cpy scnt
    bne @scopy
    dec sd_idx
    bne @strip
    lda #0
    sta stream_req
@nostream:

    ; Set scroll after the $2006 writes this frame. On the battle screen the
    ; scroll is fixed at (0,0); on the field, camX high bit selects which
    ; nametable is top-left and scrollY is the camera's vertical position.
    bit PPUSTATUS
    lda in_battle       ; only the battle screen is fixed at (0,0); a field box
    bne @fixedscroll    ; is drawn in place over the normally-scrolled map
    lda camX_lo
    sta PPUSCROLL
    lda scrollY
    sta PPUSCROLL
    lda #%10001000
    ora camX_hi
    sta PPUCTRL
    jmp @scrolldone
@fixedscroll:           ; battle screen / open field box: NT0 at scroll (0,0)
    lda #$00
    sta PPUSCROLL
    sta PPUSCROLL
    lda #%10001000
    sta PPUCTRL
@scrolldone:

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
    sta ent_gx,x        ; start on open grass, top-left screen
    lda #9
    sta ent_gy,x
    lda #4 * 16
    sta ent_px,x        ; world pixel position = cell * 16
    lda #0
    sta ent_pxh,x       ; left screen -> high bit clear
    lda #9 * 16
    sta ent_py,x
    lda #0
    sta ent_pyh,x       ; top half of the world -> high bit clear
    lda #DIR_DOWN
    sta ent_dir,x
    lda #ST_IDLE
    sta ent_state,x

    ; the wandering cat NPC
    ldx #CAT
    lda #CAT_START_GX
    sta ent_gx,x
    lda #CAT_START_GY
    sta ent_gy,x
    lda #CAT_START_GX * 16
    sta ent_px,x
    lda #0
    sta ent_pxh,x
    lda #CAT_START_GY * 16
    sta ent_py,x
    lda #0
    sta ent_pyh,x
    lda #DIR_RIGHT      ; the art's native facing
    sta ent_dir,x
    lda #ST_IDLE
    sta ent_state,x
    lda #1
    sta rng             ; LFSR seed (must be nonzero)

    lda #0
    sta stream_req      ; no pending row stream
    jsr UpdateCamera    ; seed the camera before the first frame
    lda cam_ty
    sta prev_cam_ty     ; no spurious crossing on the first frame

    lda #0              ; start equipped with weapon 0 (Club)
    sta equipped
    lda weapon_atk
    sta player_atk
    lda #PLAYER_MAX_HP
    sta player_hp

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
    bcc :+
    rts
:
    ; The other walker blocks too (two walkers: HERO=0, CAT=1). Its committed
    ; cell is its slide DESTINATION (see @go); while it slides, the cell it is
    ; leaving is still occupied on screen, so that origin blocks as well.
    txa
    eor #$01
    tay
    lda ent_gx,y
    cmp newgx
    bne @chkslide
    lda ent_gy,y
    cmp newgy
    bne @chkslide
    rts                 ; target = other's cell
@chkslide:
    lda ent_state,y
    cmp #ST_MOVE
    bne @notheld
    lda ent_gx,y        ; origin = its cell stepped opposite its direction
    sta tpx
    lda ent_gy,y
    sta tpy
    lda ent_dir,y
    cmp #DIR_UP
    bne :+
    inc tpy             ; moving up: origin below
    lda tpy
    cmp #WORLD_H
    bcc @cmporig
    lda #0
    sta tpy
    beq @cmporig
:   cmp #DIR_DOWN
    bne :+
    dec tpy             ; moving down: origin above
    bpl @cmporig
    lda #WORLD_H - 1
    sta tpy
    bne @cmporig
:   cmp #DIR_LEFT
    bne :+
    inc tpx             ; moving left: origin to the right
    lda tpx
    cmp #WORLD_W
    bcc @cmporig
    lda #0
    sta tpx
    beq @cmporig
:   dec tpx             ; moving right: origin to the left
    bpl @cmporig
    lda #WORLD_W - 1
    sta tpx
@cmporig:
    lda tpx
    cmp newgx
    bne @notheld
    lda tpy
    cmp newgy
    bne @notheld
    rts                 ; target = the cell the other is still leaving
@notheld:

    ; The cat never leaves its home box.
    cpx #CAT
    bne @go
    lda newgx
    cmp #CAT_MIN_GX
    bcc @boxout
    cmp #CAT_MAX_GX + 1
    bcs @boxout
    lda newgy
    cmp #CAT_MIN_GY
    bcc @boxout
    cmp #CAT_MAX_GY + 1
    bcc @go
@boxout:
    rts
@go:
    ; Commit the destination cell NOW (not at slide end) so no other walker
    ; can step into it mid-slide; the pixel position still slides there. All
    ; cell-based interactions (encounters, Talk) resolve only when idle, so
    ; they never see the in-flight cell.
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

; Slide the hero MOVE_SPEED pixels in ent_dir. World position is canonical and
; wraps: X is 16-bit (mod 512 = two-screen world width), Y is 16-bit (mod 480 =
; two-screen world height). When 16px have been covered, snap the grid cell from
; the world position. X = entity index.
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
    lda ent_py,x        ; up: 16-bit subtract, wrap below 0 -> 478
    sec
    sbc #MOVE_SPEED
    sta ent_py,x
    lda ent_pyh,x
    sbc #0
    sta ent_pyh,x
    bpl @tick           ; >= 0 -> fine
    lda ent_py,x        ; underflowed: + 480 ($01E0)
    clc
    adc #$E0
    sta ent_py,x
    lda ent_pyh,x
    adc #$01
    sta ent_pyh,x
    jmp @tick
@down:
    lda ent_py,x        ; down: 16-bit add, wrap at 480 -> 0
    clc
    adc #MOVE_SPEED
    sta ent_py,x
    lda ent_pyh,x
    adc #0
    sta ent_pyh,x
    cmp #$01            ; worldY >= 480 ? (hi == 1 and lo >= 224)
    bne @tick
    lda ent_py,x
    cmp #$E0
    bcc @tick
    lda #0              ; wrap to world Y = 0
    sta ent_py,x
    sta ent_pyh,x

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
    lda ent_pyh,x       ; gy = worldY / 16 = (pyh*16) | (py >> 4)
    asl a
    asl a
    asl a
    asl a
    sta ent_gy,x
    lda ent_py,x
    lsr a
    lsr a
    lsr a
    lsr a
    ora ent_gy,x
    sta ent_gy,x
    lda #ST_IDLE
    sta ent_state,x
    cpx #HERO
    bne @done
    inc step_count      ; only the hero's steps feed the encounter counter
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
;
; Walk cycle: the hero animates constantly (DQ-style), toggling between the two
; authored frames — every 8 frames while sliding (one stride per 16px step) and
; every 16 frames at rest. Frame 1's tiles sit HERO_FRAME_OFF above frame 0's.
.proc BuildOAM
    ldx #HERO
    lda ent_state,x
    cmp #ST_MOVE
    bne @idle
    lda frame_count     ; moving: toggle every 8 frames (bit 3...
    asl a               ; ...shifted up into bit 4)
    jmp @pick
@idle:
    lda frame_count     ; idle: toggle every 16 frames (bit 4)
@pick:
    and #%00010000
    beq @frame0
    lda #HERO_FRAME_OFF
@frame0:
    sta sprfrm          ; 0 or HERO_FRAME_OFF

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
    ; Y (screen) = 112 + slot_dy - 1. The camera keeps the hero centered on
    ; both axes, so its screen position is fixed and the world scrolls beneath.
    lda #112
    clc
    adc slot_dy,x
    sec
    sbc #1
    ldy oamoff
    sta oam,y

    ; tile = dir_tiles[sprbase + slot] + walk-frame offset
    txa
    clc
    adc sprbase
    tay
    lda dir_tiles,y
    clc
    adc sprfrm
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
; BuildCatOAM — draw the cat NPC into OAM slots 4-7 at its camera-relative
; screen position (torus-aware on both axes), animating its 4 frames at
; ~7.5 fps. The art faces right; walking left sets H-flip and swaps the tile
; columns (slot eor 1). Hidden when off-screen or under an open text box
; (sprites would draw over the BG-rendered window).
; ----------------------------------------------------------------------------
.proc BuildCatOAM
    ldx #CAT
    ; screen X = catX - camX (mod 512); visible iff 0..239
    lda ent_px,x
    sec
    sbc camX_lo
    sta tpx
    lda ent_pxh,x
    sbc camX_hi
    and #$01
    beq :+
    jmp @hide
:   lda tpx
    cmp #240
    bcc :+
    jmp @hide
:   ; screen Y = catY - camY (mod 480); visible iff 0..223
    lda ent_py,x
    sec
    sbc cam_y_lo
    sta tpy
    lda ent_pyh,x
    sbc cam_y_hi
    bpl @ywrapped
    pha                 ; negative: + 480 ($01E0)
    lda tpy
    clc
    adc #$E0
    sta tpy
    pla
    adc #$01
@ywrapped:
    bne @hide           ; high byte set -> outside the visible window
    lda tpy
    cmp #224
    bcs @hide
    ; under an open text box (screen rows 160-223)? the box owns that area
    lda box_open
    beq @visible
    lda tpy
    cmp #145            ; 145..223: sprite bottom (y+15) reaches row 160
    bcs @hide
@visible:
    ; animation frame (frame_count/8 mod 4) -> base tile of the 2x2 block
    lda frame_count
    lsr a
    lsr a
    lsr a
    and #$03
    asl a
    asl a
    clc
    adc #CAT_TILE_BASE
    sta sprbase
    ; facing: the art is right-facing; flip when it last walked left
    lda ent_dir,x
    cmp #DIR_LEFT
    beq @flip
    lda #$01            ; sprite palette 1
    sta sprattr
    lda #$00
    sta sprfrm          ; no column swap
    beq @slots          ; (branch always)
@flip:
    lda #$41            ; sprite palette 1 + H-flip
    sta sprattr
    lda #$01
    sta sprfrm          ; swap tile columns (slot eor 1)
@slots:
    ldx #$00            ; slot 0..3 (TL, TR, BL, BR)
    lda #16             ; OAM byte offset of hardware sprite 4
    sta oamoff
@slot:
    lda tpy
    clc
    adc slot_dy,x
    sec
    sbc #1              ; stored Y = screenY - 1
    ldy oamoff
    sta oam,y
    txa
    eor sprfrm          ; eor 1 swaps TL/TR and BL/BR when flipped
    clc
    adc sprbase
    sta oam+1,y
    lda sprattr
    sta oam+2,y
    lda tpx
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
@hide:
    lda #$FF
    sta oam+16
    sta oam+20
    sta oam+24
    sta oam+28
    rts
.endproc

; ----------------------------------------------------------------------------
; UpdateCamera — center the camera on the hero (held at screen 128,112) so the
; world scrolls beneath it.
;   camX = heroWorldX - 128 (mod 512) -> camX_lo + camX_hi (nametable select)
;   camY = heroWorldY - 112 (mod 480) -> cam_y_lo/hi; then:
;     scrollY = camY mod 240  (position within the row-streamed nametable)
;     cam_ty  = camY / 8       (camera's top tile-row, for the streamer)
; ----------------------------------------------------------------------------
.proc UpdateCamera
    ldx #HERO
    ; --- horizontal ---
    lda ent_px,x
    sec
    sbc #128
    sta camX_lo
    lda ent_pxh,x
    sbc #0
    and #$01            ; mod 512: keep only bit 8 (handles the borrow case)
    sta camX_hi

    ; --- vertical: camY = heroWorldY - 112, wrap into 0..479 ---
    lda ent_py,x
    sec
    sbc #112
    sta cam_y_lo
    lda ent_pyh,x
    sbc #0
    sta cam_y_hi
    bpl @nowrap
    lda cam_y_lo        ; underflowed -> + 480 ($01E0)
    clc
    adc #$E0
    sta cam_y_lo
    lda cam_y_hi
    adc #$01
    sta cam_y_hi
@nowrap:

    ; scrollY = camY mod 240 (subtract 240 once if camY >= 240)
    lda cam_y_hi
    bne @sub
    lda cam_y_lo
    cmp #240
    bcc @lt
@sub:
    lda cam_y_lo
    sec
    sbc #240
    sta scrollY
    jmp @mrow
@lt:
    lda cam_y_lo
    sta scrollY

    ; cam_ty = camY / 8 = (cam_y_hi << 5) | (cam_y_lo >> 3)
@mrow:
    lda cam_y_lo
    lsr a
    lsr a
    lsr a
    sta cam_ty
    lda cam_y_hi
    beq @done
    lda cam_ty
    clc
    adc #32
    sta cam_ty
@done:
    rts
.endproc

; ----------------------------------------------------------------------------
; StreamRows — when the camera crosses an 8px tile-row boundary, queue the
; incoming tile-row's strips for the NMI (2 tile + 2 attribute). Streaming at
; tile (not metatile) granularity keeps the unavoidable wrap-seam <= 7px, so it
; stays inside the top/bottom overscan instead of flashing on screen. The
; nametable holds exactly 30 tile-rows, so world tile-row T lives in slot T%30.
; ----------------------------------------------------------------------------
.proc StreamRows
    lda in_battle       ; never stream field rows onto the battle/box screen
    ora box_open
    bne @none
    lda cam_ty
    cmp prev_cam_ty
    beq @none           ; no crossing this frame

    ; Incoming world tile-row:
    ;   moving down: new bottom row = cam_ty + 29 (mod 60)
    ;   moving up:   new top row    = cam_ty
    ; "down" iff cam_ty == (prev_cam_ty + 1) mod 60.
    lda prev_cam_ty
    clc
    adc #1
    cmp #60
    bcc :+
    lda #0
:   cmp cam_ty
    bne @up
    lda cam_ty          ; down
    clc
    adc #29
    cmp #60
    bcc @setrow
    sbc #60             ; carry set here -> mod 60
    jmp @setrow
@up:
    lda cam_ty
@setrow:
    sta stream_row
    lda cam_ty
    sta prev_cam_ty
    jsr BuildStream
    rts
@none:
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
    jsr UpdateHero
    jsr CatTick         ; the cat wanders (field only; frozen in menus/battle)
    jsr WaterTick       ; shimmer the water palette (field only)

    ; Interactions/encounters only resolve when the hero is grid-aligned.
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

    ; A opens the command menu (Talk / Equip).
    lda pad1_new
    and #BTN_A
    beq @ret
    lda #MENU_CMD
    jsr OpenMenuBox
@ret:
    rts

@encounter:
    lda #0
    sta step_count
    jsr EnterBattle
    rts

@bwait:
    ; A battle message is on screen. Flush a pending HP-window update first
    ; (the VRAM buffer is free in this wait state), then A advances combat
    ; per battle_phase.
    lda hp_dirty
    beq @bw_input
    jsr UpdateHpWindow
    lda #0
    sta hp_dirty
    rts
@bw_input:
    lda pad1_new
    and #BTN_A
    bne :+
    rts
:   lda battle_phase
    cmp #BP_DEFEATED
    beq @bw_done
    cmp #BP_DEAD
    beq @bw_defeat
    cmp #BP_MENU
    bne :+
    jsr OpenBattleMenu      ; back to the Fight/Run menu
    rts
:   cmp #BP_ENEMYTURN
    bne :+
    jmp @bw_enemyturn
:   cmp #BP_FLED
    bne :+
    jsr ExitBattle          ; fled: straight back to the field
    rts
:   cmp #BP_DYING
    beq @bw_dying
    cmp #BP_PLAYERDEAD
    bne @bw_ret
    lda #PLAYER_MAX_HP      ; revive and wake back on the field
    sta player_hp
    jsr ExitBattle
@bw_ret:
    rts
@bw_defeat:
    lda #MSG_SLIME_DEFEATED
    jsr SetMessage
    lda #BP_DEFEATED
    sta battle_phase
    jmp @bw_show
@bw_dying:
    lda #MSG_DEAD
    jsr SetMessage
    lda #BP_PLAYERDEAD
    sta battle_phase
    jmp @bw_show
@bw_done:
    lda #0
    sta job_step
    lda #GS_ENEMYDIE        ; erase the enemy, then ExitBattle
    sta gamestate
    rts
@bw_enemyturn:
    ; The slime strikes back for 1-2 damage, floored at 0 HP.
    lda frame_count
    and #$01
    clc
    adc #1
    sta last_damage
    lda player_hp
    sec
    sbc last_damage
    bcs :+
    lda #0
:   sta player_hp
    lda #1
    sta hp_dirty            ; status window redraws once the message is up
    jsr ComposeEnemyHit
    lda #<msg_buf
    sta msg_ptr
    lda #>msg_buf
    sta msg_ptr+1
    lda player_hp
    beq @bw_todying
    lda #BP_MENU
    sta battle_phase
    jmp @bw_show
@bw_todying:
    lda #BP_DYING
    sta battle_phase
@bw_show:
    lda #0
    sta cur_line
    lda #GS_TEXT
    sta gamestate
    rts

@enemydie:
    ; Erase the enemy one tile-row per frame through the VRAM buffer.
    jsr EraseEnemyRow
    inc job_step
    lda job_step
    cmp #4
    bcs :+
    rts
:   lda #DIE_DELAY
    sta battle_timer
    lda #GS_BATTLEWAIT
    sta gamestate
    rts

@battlewait:
    dec battle_timer
    beq :+
    rts
:   jsr ExitBattle      ; cut back to the field at the prior position
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
    lda battle_phase
    cmp #BP_INTRO
    bne :+
    jsr OpenBattleMenu  ; intro shown: straight to the Fight/Run menu
    rts
:   lda #GS_BWAIT       ; battle: wait for A to drive combat
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
    beq :+
    jmp @m_cancel
:   lda pad1_new
    and #BTN_A
    bne :+
    rts
:
    ; --- A: confirm the highlighted item ---
    lda menu_id
    cmp #MENU_EQUIP
    beq @m_equip
    cmp #MENU_BATTLE
    bne :+
    jmp @m_battle
:   ; command menu
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
@m_battle:
    lda menu_cursor
    bne @m_run
    ; Fight: deal damage, then let the enemy answer (or die)
    jsr DoAttack        ; damage + "takes N damage" line into msg_buf
    lda #<msg_buf
    sta msg_ptr
    lda #>msg_buf
    sta msg_ptr+1
    lda #CTX_BATTLE
    sta msg_context
    lda enemy_hp
    beq @m_edead
    lda #BP_ENEMYTURN
    bne @m_bset         ; (branch always)
@m_edead:
    lda #BP_DEAD
@m_bset:
    sta battle_phase
    jmp @m_showmsg
@m_run:
    lda #CTX_BATTLE
    sta msg_context
    lda #MSG_FLEE
    jsr SetMessage
    lda #BP_FLED
    sta battle_phase
@m_showmsg:
    lda #0
    sta cur_line
    lda #GS_TEXT
    sta gamestate
    rts
@m_cancel:
    lda menu_id
    cmp #MENU_BATTLE
    bne :+
    rts                 ; no backing out of a battle with B
:   cmp #MENU_EQUIP
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
    lda #1              ; draw mode = close (restore the map under the box)
    sta draw_mode
    jsr DrawStep
    inc job_step
    lda job_step
    cmp #WIN_STEPS
    bcc @ret6
    lda #0
    sta box_open        ; box fully removed; resume field streaming
    lda #GS_FIELD
    sta gamestate
@ret6:
    rts
.endproc

; ----------------------------------------------------------------------------
; CatTick — wander AI for the cat NPC. While sliding, keep sliding. While
; idle, clock the LFSR every frame (so decisions vary with when the player
; moves) and roughly once a second either amble one cell in a random
; direction or stay put. TryStep enforces terrain, the hero's cell, and the
; cat's home box.
; ----------------------------------------------------------------------------
.proc CatTick
    ldx #CAT
    lda ent_state,x
    cmp #ST_MOVE
    bne @idle
    jsr StepMove
    rts
@idle:
    lda rng             ; clock the LFSR (taps $1D)
    asl a
    bcc :+
    eor #$1D
:   sta rng
    lda frame_count
    and #$3F
    beq @decide
    rts
@decide:
    lda rng
    and #$07
    cmp #4
    bcs @stay           ; half the time: sit still
    sta ent_dir,x       ; 0..3 matches DIR_UP/DOWN/LEFT/RIGHT
    jsr TryStep
@stay:
    rts
.endproc

; ----------------------------------------------------------------------------
; WaterTick — animate the water: every 16 frames queue a 2-byte palette packet
; cycling BG palette 1's two blues ($3F05-$3F06) through a 4-phase table.
; Runs only in GS_FIELD, where the VRAM buffer is otherwise idle (the battle
; palette reuses those slots for the enemy, so it must not run there).
; ----------------------------------------------------------------------------
.proc WaterTick
    lda frame_count
    and #$0F
    beq :+
    rts
:   lda frame_count     ; phase = (frame_count / 16) mod 4
    lsr a
    lsr a
    lsr a
    lsr a
    and #$03
    tax
    lda #$3F
    sta VBUF
    lda #$05
    sta VBUF+1
    lda #2
    sta VBUF+2
    lda water_c1,x
    sta VBUF+3
    lda water_c2,x
    sta VBUF+4
    rts
.endproc

.segment "RODATA"
water_c1:               ; light-blue wave color per phase
    .byte $21, $2C, $21, $2C
water_c2:               ; deep-blue base color per phase
    .byte $11, $01, $11, $01

.segment "CODE"

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

; DoAttack — deal the equipped weapon's attack power (with a -1 wobble from
; the frame parity) to the enemy, capped to remaining HP, and compose the
; "takes N damage" line.
.proc DoAttack
    lda frame_count
    lsr a               ; carry = frame parity
    lda player_atk
    sbc #0              ; atk or atk-1
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

; OpenMenuBox — set up menu A and open the box (used from the field). The box is
; drawn in place over the scrolled map, so just compute its on-screen geometry,
; freeze streaming, and let GS_OPENING animate it in.
.proc OpenMenuBox
    sta menu_id
    jsr ComputeBoxGeom  ; box position for the current camera
    lda #1
    sta box_open        ; freeze row-streaming while the box is up
    lda #0
    sta stream_req      ; drop any field row-stream queued this frame
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
    cmp #MENU_BATTLE
    bne :+
    jmp @battle
:
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

@battle:
    ; battle menu: Fight / Run
    ldx #0
    jsr EmitCursor
    lda #<frag_OPT_FIGHT
    sta ptr
    lda #>frag_OPT_FIGHT
    sta ptr+1
    jsr CopyFrag
    lda #MSG_NEWLINE
    jsr StoreDst
    ldx #1
    jsr EmitCursor
    lda #<frag_OPT_RUN
    sta ptr
    lda #>frag_OPT_RUN
    sta ptr+1
    jsr CopyFrag
    lda #MSG_NEWLINE
    jsr StoreDst
    lda #MSG_NEWLINE     ; line 2 blank
    jsr StoreDst
    lda #MSG_END         ; line 3 blank + end
    jsr StoreDst
    rts
.endproc

; OpenBattleMenu — (re)compose and show the Fight/Run menu in the already-open
; battle box. Cursor resets to Fight.
.proc OpenBattleMenu
    lda #MENU_BATTLE
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
    sta cur_line
    lda #GS_TEXT
    sta gamestate
    rts
.endproc

; ComposeEnemyHit — build "<EATK_PRE><last_damage><EATK_POST>" + 3 blank lines
; + end into msg_buf, ready for RenderLine.
.proc ComposeEnemyHit
    lda #<msg_buf
    sta dst
    lda #>msg_buf
    sta dst+1
    lda #<frag_EATK_PRE
    sta ptr
    lda #>frag_EATK_PRE
    sta ptr+1
    jsr CopyFrag
    lda last_damage
    sta num
    jsr AppendNumber
    lda #<frag_EATK_POST
    sta ptr
    lda #>frag_EATK_POST
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

; UpdateHpWindow — queue a VRAM packet rewriting the status window's interior
; row ("HP dd") on the battle screen. Battle only (fixed nametable address).
.proc UpdateHpWindow
    jsr ComposeHpRow    ; 6 tiles into msg_buf
    lda #$20
    sta VBUF
    lda #$63
    sta VBUF+1
    lda #6
    sta VBUF+2
    ldx #0
:   lda msg_buf,x
    sta VBUF+3,x
    inx
    cpx #6
    bne :-
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

; RenderLine — render interior line cur_line of the current message into linebuf
; (padded to TEXT_COLS), then queue it into the box's row over the scrolled map,
; split at the seam. term_action is set from the ending control code:
; 0 = newline, 1 = page break, 2 = end. Interior line L is box row 2+L.
.proc RenderLine
    ldx #0              ; column index into linebuf
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
    sta linebuf,x
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
    bcs @emit
    sta linebuf,x
    inx
    jmp @padloop
@emit:
    ; nt_row = (box_nt_base + 2 + cur_line) mod 30
    lda box_nt_base
    clc
    adc #2
    adc cur_line
    cmp #30
    bcc :+
    sbc #30
:   sta nt_row_tmp
    ; split [box col 1, TEXT_COLS] at the seam
    lda #TEXT_COLS
    sta sr_cnt
    lda box_cstart
    clc
    adc #1
    and #$3F
    jsr SplitRange
    ldx #0              ; segment 1 -> descriptor 0, source = linebuf
    lda sg1_base
    sta tpx
    lda nt_row_tmp
    sta tpy
    lda sg1_col
    sta mt_col
    lda sg1_cnt
    sta mt_row
    lda #<linebuf
    sta ptr
    lda #>linebuf
    sta ptr+1
    jsr PutSeg
    lda sg2_cnt
    beq @one
    ldx #1              ; segment 2 -> descriptor 1, source = linebuf + sg1_cnt
    lda sg2_base
    sta tpx
    lda nt_row_tmp
    sta tpy
    lda #0
    sta mt_col
    lda sg2_cnt
    sta mt_row
    lda #<linebuf
    clc
    adc sg1_cnt
    sta ptr
    lda #>linebuf
    adc #0
    sta ptr+1
    jsr PutSeg
    lda #2
    sta stream_req
    rts
@one:
    lda #1
    sta stream_req
    rts
.endproc

; DrawPrompt / ErasePrompt — the "more text" triangle on the box's bottom border
; (box row 7, column 15), drawn in place over the scrolled map.
.proc DrawPrompt
    lda #ARROW_TILE
    jmp PromptTile
.endproc

.proc ErasePrompt
    lda #WIN_BOTTOM_TILE
    jmp PromptTile
.endproc

; PromptTile — write tile A at box row 7, column 15 (one tile, one nametable).
.proc PromptTile
    sta linebuf         ; 1-byte source
    lda box_nt_base
    clc
    adc #7
    cmp #30
    bcc :+
    sbc #30
:   sta tpy             ; nt_row
    lda box_cstart
    clc
    adc #15
    and #$3F            ; nametable column of box col 15
    cmp #32
    bcc @nt0
    sec
    sbc #32
    sta mt_col
    lda #$24
    sta tpx
    jmp @put
@nt0:
    sta mt_col
    lda #$20
    sta tpx
@put:
    lda #1
    sta mt_row
    lda #<linebuf
    sta ptr
    lda #>linebuf
    sta ptr+1
    ldx #0
    jsr PutSeg
    lda #1
    sta stream_req
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

; DrawStep — one animation step of the in-place text box (job_step 0..8). The
; box is drawn over the scrolled map and restored on close; to avoid ever showing
; a tile under the wrong palette, transitions go through all-black:
;   steps 0-3 : clear the 8 box rows to black tiles (2 rows/step)
;   step  4   : set the box attribute region (palette 3 open / map palette close)
;   steps 5-8 : draw the real content (2 rows/step)
; Each row is queued as 1-2 stream descriptors (split at the scroll seam) for the
; NMI to write. draw_mode 0 = open (window shell), 1 = close (restore the map).
.proc DrawStep
    lda job_step
    cmp #4
    bne :+
    jmp @attr
:   bcc @clear          ; 0-3
    sec                 ; 5-8: content
    sbc #5
    sta woff            ; k
    lda draw_mode
    beq @shell
    lda #2
    sta bx_phase        ; restore the map (close)
    jmp @rows
@shell:
    lda #1
    sta bx_phase        ; window shell (open)
    jmp @rows
@clear:
    sta woff            ; k = job_step (0-3)
    lda #0
    sta bx_phase
@rows:
    lda #0
    sta bs_cnt          ; descriptor index
    lda woff
    asl a               ; j0 = k*2
    pha
    jsr QueueBoxTileRow
    pla
    clc
    adc #1              ; j1
    jsr QueueBoxTileRow
    lda bs_cnt
    sta stream_req
    rts
@attr:
    jsr DrawBoxAttr
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

    lda #1
    sta in_battle       ; set before NMI resumes so it uses battle scroll (0,0)
    lda #0
    sta stream_req      ; discard any field row-stream queued this frame

    bit PPUSTATUS       ; reset scroll before rendering resumes
    lda #$00
    sta PPUSCROLL
    sta PPUSCROLL

    lda #%10001000
    sta PPUCTRL         ; NMI on, sprite pattern table 1
    lda #%00011110
    sta PPUMASK         ; rendering on

    ; Begin combat: set up state, then open the message box and show the intro.
    jsr ComputeBoxGeom  ; box geometry for the battle screen (fixed at row 20)
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

    ; --- hero status window (DQ-style): rows 2-4, cols 2-9, "HP dd" ---
    jsr ComposeHpRow    ; interior row (6 tiles) into msg_buf
    bit PPUSTATUS
    lda #$20            ; row 2: top border
    sta PPUADDR
    lda #$42
    sta PPUADDR
    lda #WIN_TL_TILE
    sta PPUDATA
    lda #WIN_T_TILE
    ldx #6
:   sta PPUDATA
    dex
    bne :-
    lda #WIN_TR_TILE
    sta PPUDATA
    lda #$20            ; row 3: L + "HP dd " + R
    sta PPUADDR
    lda #$62
    sta PPUADDR
    lda #WIN_L_TILE
    sta PPUDATA
    ldx #0
:   lda msg_buf,x
    sta PPUDATA
    inx
    cpx #6
    bne :-
    lda #WIN_R_TILE
    sta PPUDATA
    lda #$20            ; row 4: bottom border
    sta PPUADDR
    lda #$82
    sta PPUADDR
    lda #WIN_BL_TILE
    sta PPUDATA
    lda #WIN_BOTTOM_TILE
    ldx #6
:   sta PPUDATA
    dex
    bne :-
    lda #WIN_BR_TILE
    sta PPUDATA
    ; status-window attributes -> palette 3 ($23C0-$23C2, $23C8-$23CA; the
    ; rest of those 32px blocks is blank backdrop, so palette is moot there)
    lda #$23
    sta PPUADDR
    lda #$C0
    sta PPUADDR
    lda #$FF
    sta PPUDATA
    sta PPUDATA
    sta PPUDATA
    lda #$23
    sta PPUADDR
    lda #$C8
    sta PPUADDR
    lda #$FF
    sta PPUDATA
    sta PPUDATA
    sta PPUDATA
    rts
.endproc

; ----------------------------------------------------------------------------
; ComposeHpRow — build the status-window interior row "HP dd" into msg_buf,
; padded with blanks so the first 6 bytes are always valid tiles.
; ----------------------------------------------------------------------------
.proc ComposeHpRow
    lda #<msg_buf
    sta dst
    lda #>msg_buf
    sta dst+1
    lda #<frag_LBL_HP
    sta ptr
    lda #>frag_LBL_HP
    sta ptr+1
    jsr CopyFrag        ; "HP"
    lda #$00
    jsr StoreDst        ; space
    lda player_hp
    sta num
    jsr AppendNumber    ; 1-2 digits
    lda #$00            ; pad: a 1-digit HP still fills all 6 tiles
    jsr StoreDst
    lda #$00
    jsr StoreDst
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

    jsr UpdateCamera    ; recompute field scroll from the hero's world position
    jsr DrawField       ; repaint the field at that camera (camera-aware)
    lda cam_ty
    sta prev_cam_ty     ; no spurious stream on the first field frame back
    lda #<pal_field
    sta ptr
    lda #>pal_field
    sta ptr+1
    jsr LoadPalette

    ; Rebuild the hero and cat sprites and push them before rendering resumes.
    jsr BuildOAM
    jsr BuildCatOAM
    lda #$00
    sta OAMADDR
    lda #>OAM_BUF
    sta OAMDMA

    lda #$00
    sta in_battle       ; clear before NMI resumes so it uses field scroll

    bit PPUSTATUS       ; restore the field scroll position
    lda camX_lo
    sta PPUSCROLL
    lda scrollY
    sta PPUSCROLL

    lda #%10001000
    ora camX_hi
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
; HideHero — park the hero's and the cat's metasprite entries off-screen
; (battle screen).
; ----------------------------------------------------------------------------
.proc HideHero
    lda #$FF
    sta oam+0
    sta oam+4
    sta oam+8
    sta oam+12
    sta oam+16
    sta oam+20
    sta oam+24
    sta oam+28
    rts
.endproc

; ----------------------------------------------------------------------------
; DrawField — repaint the whole field for the CURRENT camera (cam_ty): for each
; of the 30 visible world tile-rows T = cam_ty+i (mod 60), write its LEFT/RIGHT
; strips into nametable slot T mod 30, then rebuild the attribute shadows. Used
; at boot and when returning from battle. Rendering off only.
; ----------------------------------------------------------------------------
.proc DrawField
    lda #0
    sta tpx             ; i = 0..29
@row:
    lda cam_ty          ; T = (cam_ty + i) mod 60
    clc
    adc tpx
    cmp #60
    bcc :+
    sbc #60
:   sta tpy             ; tpy = T
    cmp #30             ; slot = T mod 30
    bcc :+
    sbc #30
:   sta mt_col          ; mt_col = slot

    lda #0              ; src = worldtiles + T*64
    sta ms_hi
    lda tpy
    sta ms_lo
    ldx #6
@s1:
    asl ms_lo
    rol ms_hi
    dex
    bne @s1
    lda ms_lo
    clc
    adc #<worldtiles
    sta ptr
    lda ms_hi
    adc #>worldtiles
    sta ptr+1

    lda #0              ; rowbase = slot*32
    sta rb_hi
    lda mt_col
    sta rb_lo
    ldx #5
@s2:
    asl rb_lo
    rol rb_hi
    dex
    bne @s2

    bit PPUSTATUS       ; LEFT 32 -> $2000 + rowbase
    lda #$20
    clc
    adc rb_hi
    sta PPUADDR
    lda rb_lo
    sta PPUADDR
    ldy #0
@l: lda (ptr),y
    sta PPUDATA
    iny
    cpy #32
    bne @l

    bit PPUSTATUS       ; RIGHT 32 -> $2400 + rowbase (src + 32)
    lda #$24
    clc
    adc rb_hi
    sta PPUADDR
    lda rb_lo
    sta PPUADDR
    ldy #32
@r: lda (ptr),y
    sta PPUDATA
    iny
    cpy #64
    bne @r

    inc tpx
    lda tpx
    cmp #30
    beq :+
    jmp @row
:   jsr InitAttrShadow
    rts
.endproc

; InitAttrShadow — rebuild the attribute shadows for the 30 visible tile-rows
; (cam_ty..cam_ty+29) and copy them to both nametables. Rendering off only.
.proc InitAttrShadow
    ldx #63             ; clear both shadows
    lda #0
@clr:
    sta attr_shadow_l,x
    sta attr_shadow_r,x
    dex
    bpl @clr

    lda #0
    sta attr_force      ; use the map's palettes, not the box fill
    sta tpx             ; tile-row index i = 0..29 (MergeAttrRow clobbers X/Y)
@m:
    lda cam_ty          ; T = (cam_ty + i) mod 60
    clc
    adc tpx
    cmp #60
    bcc :+
    sbc #60
:   lsr a               ; MY = T / 2
    jsr MergeAttrRow
    inc tpx
    lda tpx
    cmp #30
    bne @m

    bit PPUSTATUS       ; left attributes -> $23C0
    lda #$23
    sta PPUADDR
    lda #$C0
    sta PPUADDR
    ldx #0
@wl:
    lda attr_shadow_l,x
    sta PPUDATA
    inx
    cpx #64
    bne @wl

    bit PPUSTATUS       ; right attributes -> $27C0
    lda #$27
    sta PPUADDR
    lda #$C0
    sta PPUADDR
    ldx #0
@wr:
    lda attr_shadow_r,x
    sta PPUDATA
    inx
    cpx #64
    bne @wr
    rts
.endproc

; MergeAttrRow — fold world metatile-row MY (in A) into the attribute shadows.
; One metatile is one attr quadrant, so an attr byte mixes two metatile rows:
; an even nametable row writes the low nibble, an odd row the high nibble. The
; nametable slot is nmr = MY mod 15. Leaves abase (= (nmr/2)*8) in sd_idx for the
; caller. Clobbers A, X, Y, rb_lo, rb_hi, bs_par, bs_cnt.
.proc MergeAttrRow
    sta bs_par          ; bs_par = MY
    cmp #15             ; nmr = MY mod 15  (MY < 30 -> one subtract)
    bcc :+
    sbc #15
:   sta rb_lo           ; rb_lo = nmr
    lsr a               ; abase = (nmr/2)*8
    asl a
    asl a
    asl a
    sta sd_idx
    lda rb_lo           ; parity = nmr & 1
    and #$01
    sta rb_hi
    lda bs_par          ; pbase = MY*8 -> Y
    asl a
    asl a
    asl a
    tay
    ldx sd_idx          ; shadow index -> X
    lda #8
    sta bs_cnt
    lda rb_hi
    bne @odd
@even:
    jsr @pairL          ; low nibble = left/right metatile palettes
    sta mt_col
    lda attr_shadow_l,x
    and #$F0
    ora mt_col
    sta attr_shadow_l,x
    jsr @pairR
    sta mt_col
    lda attr_shadow_r,x
    and #$F0
    ora mt_col
    sta attr_shadow_r,x
    inx
    iny
    dec bs_cnt
    bne @even
    rts
@odd:
    jsr @pairL          ; high nibble
    asl a
    asl a
    asl a
    asl a
    sta mt_col
    lda attr_shadow_l,x
    and #$0F
    ora mt_col
    sta attr_shadow_l,x
    jsr @pairR
    asl a
    asl a
    asl a
    asl a
    sta mt_col
    lda attr_shadow_r,x
    and #$0F
    ora mt_col
    sta attr_shadow_r,x
    inx
    iny
    dec bs_cnt
    bne @odd
    rts
; pair value for the current column (Y): the map's palettes, or $0F (palette 3,
; both quadrants) when attr_force is set (drawing a box). Preserves X, Y.
@pairL:
    lda attr_force
    bne :+
    lda attr_pair_l,y
    rts
:   lda #$0F
    rts
@pairR:
    lda attr_force
    bne :+
    lda attr_pair_r,y
    rts
:   lda #$0F
    rts
.endproc

; BuildStream — fill 4 stream descriptors for world TILE-row stream_row (the
; LEFT and RIGHT 32-tile strips + the two attribute byte-rows), then arm
; stream_req. slot = stream_row mod 30 is the nametable tile-row.
.proc BuildStream
    ; rowbase16 = slot * 32, slot = stream_row mod 30
    lda stream_row
    cmp #30
    bcc :+
    sbc #30
:   sta rb_lo
    lda #0
    sta rb_hi
    ldx #5
@sh:
    asl rb_lo
    rol rb_hi
    dex
    bne @sh

    ; source offset = stream_row * 64 + worldtiles
    lda #0
    sta ms_hi
    lda stream_row
    sta ms_lo
    ldx #6
@sh2:
    asl ms_lo
    rol ms_hi
    dex
    bne @sh2
    lda ms_lo
    clc
    adc #<worldtiles
    sta ms_lo
    lda ms_hi
    adc #>worldtiles
    sta ms_hi

    ; desc 0: LEFT strip  -> $2000 + rowbase, src ms
    lda #$20
    clc
    adc rb_hi
    sta sd_dst_hi+0
    lda rb_lo
    sta sd_dst_lo+0
    lda ms_lo
    sta sd_src_lo+0
    lda ms_hi
    sta sd_src_hi+0
    lda #32
    sta sd_cnt+0
    ; desc 1: RIGHT strip -> $2400 + rowbase, src ms + 32
    lda #$24
    clc
    adc rb_hi
    sta sd_dst_hi+1
    lda rb_lo
    sta sd_dst_lo+1
    lda ms_lo
    clc
    adc #32
    sta sd_src_lo+1
    lda ms_hi
    adc #0
    sta sd_src_hi+1
    lda #32
    sta sd_cnt+1

    ; attributes: fold this tile-row's metatile-row (stream_row / 2) into the
    ; shadows; abase (nametable attr-row * 8) returned in sd_idx.
    lda stream_row
    lsr a
    jsr MergeAttrRow

    ; desc 2: LEFT attr  -> $23C0 + abase, src attr_shadow_l + abase
    lda sd_idx
    clc
    adc #$C0
    sta sd_dst_lo+2
    lda #$23
    adc #0
    sta sd_dst_hi+2
    lda #<attr_shadow_l
    clc
    adc sd_idx
    sta sd_src_lo+2
    lda #>attr_shadow_l
    adc #0
    sta sd_src_hi+2
    lda #8
    sta sd_cnt+2
    ; desc 3: RIGHT attr -> $27C0 + abase, src attr_shadow_r + abase
    lda sd_idx
    clc
    adc #$C0
    sta sd_dst_lo+3
    lda #$27
    adc #0
    sta sd_dst_hi+3
    lda #<attr_shadow_r
    clc
    adc sd_idx
    sta sd_src_lo+3
    lda #>attr_shadow_r
    adc #0
    sta sd_src_hi+3
    lda #8
    sta sd_cnt+3

    lda #4
    sta stream_req      ; arm: the next NMI writes the 4 strips
    rts
.endproc

; ----------------------------------------------------------------------------
; Text box drawn IN PLACE over the scrolling map (Dragon-Quest style): the box
; tiles are written into the scrolled nametables and the map is restored under
; them on close -- no layout swap, no rendering-off, no flash. The box spans 8
; nametable rows (screen rows 20-27), full screen width, so each row is split
; across the two side-by-side nametables at the scroll seam. Attribute (palette)
; updates go per metatile-row through the shadow so neighbouring map tiles in the
; same attribute byte keep their colour (no bleed at the box edges).
; ----------------------------------------------------------------------------

; ComputeBoxGeom -- set the box position when it opens. field: top = screen row
; 20 -> nametable row (cam_ty+20) mod 30, left edge = camX/8. battle: fixed at
; row 20, column 0 (the battle screen is held at scroll 0,0).
.proc ComputeBoxGeom
    lda in_battle
    bne @battle
    lda cam_ty           ; world tile-row of box top = cam_ty + 20 (mod 60)
    clc
    adc #20
    cmp #60
    bcc :+
    sbc #60
:   sta box_wrow
    cmp #30              ; nametable row = that mod 30
    bcc :+
    sbc #30
:   sta box_nt_base
    lda camX_lo          ; left edge column = camX / 8 (0..63)
    lsr a
    lsr a
    lsr a
    sta box_cstart
    lda camX_hi
    beq @done
    lda box_cstart
    clc
    adc #32
    sta box_cstart
    jmp @done
@battle:
    lda #20
    sta box_wrow
    sta box_nt_base
    lda #0
    sta box_cstart
@done:
    rts
.endproc

; SplitRange -- split a screen-relative run starting at nametable column A
; (0..63), length sr_cnt, into up to two contiguous segments (one per nametable)
; at the seam. Outputs sg1_* and sg2_* (sg2_cnt = 0 when it fits in one screen).
.proc SplitRange
    cmp #32
    bcs @nt1
    sta sg1_col          ; run begins in NT0
    lda #$20
    sta sg1_base
    lda #$24
    sta sg2_base
    lda #32
    sec
    sbc sg1_col          ; tiles to the seam
    jmp @fit
@nt1:
    sec
    sbc #32
    sta sg1_col          ; run begins in NT1
    lda #$24
    sta sg1_base
    lda #$20
    sta sg2_base
    lda #32
    sec
    sbc sg1_col
@fit:
    cmp sr_cnt           ; A = room before the seam
    bcc @split
    lda sr_cnt           ; fits in one segment
    sta sg1_cnt
    lda #0
    sta sg2_cnt
    rts
@split:
    sta sg1_cnt          ; A = room
    lda sr_cnt
    sec
    sbc sg1_cnt
    sta sg2_cnt
    rts
.endproc

; PutSeg -- store one stream descriptor (index X): nametable address
; tpx:(tpy*32 + mt_col), count mt_row, source pointer (ptr).
.proc PutSeg
    lda tpy
    sta rb_lo
    lda #0
    sta rb_hi
    ldy #5
@sh:
    asl rb_lo
    rol rb_hi
    dey
    bne @sh
    lda rb_lo
    clc
    adc mt_col
    sta sd_dst_lo,x
    lda rb_hi
    adc tpx
    sta sd_dst_hi,x
    lda ptr
    sta sd_src_lo,x
    lda ptr+1
    sta sd_src_hi,x
    lda mt_row
    sta sd_cnt,x
    rts
.endproc

; QueueBoxTileRow -- queue the segments for one full-width box row (A = box row
; 0..7) into descriptors starting at bs_cnt. Source is chosen by bx_phase:
; 0 = black clear, 1 = window shell (winmap), 2 = restore the map (worldtiles).
.proc QueueBoxTileRow
    sta bs_par
    clc                  ; nt_row = (box_nt_base + j) mod 30
    adc box_nt_base
    cmp #30
    bcc :+
    sbc #30
:   sta nt_row_tmp
    lda #32              ; split the full-width row at the seam
    sta sr_cnt
    lda box_cstart
    jsr SplitRange
    lda bx_phase
    bne @notclear
    lda #<win_zeros      ; clear: both segments read zeros
    sta ptr
    sta ms_lo
    lda #>win_zeros
    sta ptr+1
    sta ms_hi
    jmp @emit
@notclear:
    cmp #2
    beq @restore
    lda bs_par           ; shell: winmap + j*32 (indexed by box column)
    asl a
    asl a
    asl a
    asl a
    asl a
    clc
    adc #<winmap
    sta ptr
    lda #0
    adc #>winmap
    sta ptr+1
    lda ptr              ; seg2 src follows seg1 by sg1_cnt
    clc
    adc sg1_cnt
    sta ms_lo
    lda ptr+1
    adc #0
    sta ms_hi
    jmp @emit
@restore:
    lda box_wrow         ; restore: worldtiles[(box_wrow+j) mod 60], by global col
    clc
    adc bs_par
    cmp #60
    bcc :+
    sbc #60
:   sta rb_lo
    lda #0
    sta rb_hi
    ldy #6
@w:
    asl rb_lo
    rol rb_hi
    dey
    bne @w
    lda rb_lo
    clc
    adc #<worldtiles
    sta ms_lo            ; ms = row base (global column 0) = seg2 src
    lda rb_hi
    adc #>worldtiles
    sta ms_hi
    lda ms_lo            ; seg1 src = row base + box_cstart (global column)
    clc
    adc box_cstart
    sta ptr
    lda ms_hi
    adc #0
    sta ptr+1
@emit:
    ldx bs_cnt           ; segment 1 -> descriptor bs_cnt
    lda sg1_base
    sta tpx
    lda nt_row_tmp
    sta tpy
    lda sg1_col
    sta mt_col
    lda sg1_cnt
    sta mt_row
    jsr PutSeg
    inc bs_cnt
    lda sg2_cnt          ; segment 2 only if the row crossed the seam
    beq @done
    ldx bs_cnt
    lda sg2_base
    sta tpx
    lda nt_row_tmp
    sta tpy
    lda #0
    sta mt_col
    lda sg2_cnt
    sta mt_row
    lda ms_lo
    sta ptr
    lda ms_hi
    sta ptr+1
    jsr PutSeg
    inc bs_cnt
@done:
    rts
.endproc

; DrawBoxAttr -- set (open) / restore (close) the box region's attributes.
; Battle: write the palette-3 window band to $23E8. Field: fold the box's 4
; metatile-rows into the shadow per nibble (palette 3 on open, the map's palette
; on close), then write the affected attribute rows from the shadow.
.proc DrawBoxAttr
    lda in_battle
    beq @field
    lda #$23
    sta sd_dst_hi
    lda #$E8
    sta sd_dst_lo
    lda #16
    sta sd_cnt
    lda #<winattr
    sta sd_src_lo
    lda #>winattr
    sta sd_src_hi
    lda #1
    sta stream_req
    rts
@field:
    lda draw_mode        ; open(0)->force palette 3 ; close(1)->restore the map
    eor #1
    sta attr_force
    lda #0
    sta woff             ; metatile-row index 0..3
@mloop:
    lda box_wrow
    lsr a                ; world metatile-row = (box_wrow/2 + i) mod 30
    clc
    adc woff
    cmp #30
    bcc :+
    sbc #30
:   jsr MergeAttrRow
    inc woff
    lda woff
    cmp #4
    bne @mloop
    lda box_nt_base      ; ar0 = box_nt_base / 4 (attribute row of box top)
    lsr a
    lsr a
    sta bs_par
    lda #0
    sta bs_cnt           ; descriptor index
    ldx #0
@wloop:
    txa
    pha
    clc
    adc bs_par
    and #7               ; attribute row (mod 8)
    jsr QueueAttrRow
    pla
    tax
    inx
    cpx #3
    bne @wloop
    lda bs_cnt
    sta stream_req
    rts
.endproc

; QueueAttrRow -- queue NT0 ($23C0) and NT1 ($27C0) writes (8 bytes each) for
; attribute row A from the shadows, into descriptors bs_cnt and bs_cnt+1.
.proc QueueAttrRow
    asl a
    asl a
    asl a                ; ar * 8 = offset into an attribute table
    sta nt_row_tmp
    ldx bs_cnt           ; NT0
    clc
    adc #$C0
    sta sd_dst_lo,x
    lda #$23
    sta sd_dst_hi,x
    lda #<attr_shadow_l
    clc
    adc nt_row_tmp
    sta sd_src_lo,x
    lda #>attr_shadow_l
    adc #0
    sta sd_src_hi,x
    lda #8
    sta sd_cnt,x
    inc bs_cnt
    ldx bs_cnt           ; NT1
    lda nt_row_tmp
    clc
    adc #$C0
    sta sd_dst_lo,x
    lda #$27
    sta sd_dst_hi,x
    lda #<attr_shadow_r
    clc
    adc nt_row_tmp
    sta sd_src_lo,x
    lda #>attr_shadow_r
    adc #0
    sta sd_src_hi,x
    lda #8
    sta sd_cnt,x
    inc bs_cnt
    rts
.endproc

; ----------------------------------------------------------------------------
; Palette data. Only $3F00 (universal backdrop) is visible for the solid
; screen; the rest are seeded so later steps have sane defaults.
; ----------------------------------------------------------------------------
.segment "RODATA"
pal_field:
    ; Background palettes:
    .byte $0F, $1A, $29, $17   ; 0: ground  - dark grass, light foliage, brown
    .byte $0F, $21, $11, $30   ; 1: water   - light blue, deep blue, white
    .byte $0F, $1A, $27, $16   ; 2: deco    - grass green, gold, red (NPC/flowers)
    .byte $0F, $30, $16, $27   ; 3: window  - white ink, red + tan (brick walls)
    ; Sprite palettes:
    .byte $0F, $0F, $27, $12   ; 0: hero - black outline, gold skin, blue tunic
    .byte $0F, $24, $15, $0F   ; 1: cat - pink, red mouth, black eyes (nesprite)
    .byte $0F, $1A, $2A, $30
    .byte $0F, $0F, $30, $0F

pal_battle:
    ; Battle backdrop = black ($0F): the classic JRPG arena, and the color the
    ; text box needs (the box's black is value 0 = the backdrop). Every color-0
    ; entry is $0F so the $3F1x->$3F0x mirror can't clobber the backdrop.
    .byte $0F, $0F, $10, $30   ; 0: blank screen
    .byte $0F, $21, $11, $30   ; 1: enemy - light blue body, deep blue shade, white
    .byte $0F, $0F, $10, $30
    .byte $0F, $30, $16, $27   ; 3: window - white ink (matches the field window)
    .byte $0F, $0F, $27, $12
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
