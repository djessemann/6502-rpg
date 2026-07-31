; battle.s — turn-based battle: up to four party members against a formation of
; up to four enemies of at most two types. Lives in PRG bank 25 ($A000).
;
; Enemies are drawn as BACKGROUND tiles (the game's whole visual hook): each
; monster type occupies one 1KB CHR bank, switched into R4 (BG tiles $80-$BF)
; and R5 ($C0-$FF). The party is a HUD at the bottom of the screen; the message
; window is the same in-place window the field uses, with the camera pinned to
; (0,0) so every text routine works unchanged.

.include "nes.inc"
.include "zp.inc"
.include "ram.inc"
.include "banks.inc"
.include "gen/charmap.inc"
.include "gen/msgids.inc"
.include "gen/dataids.inc"
.include "gen/songids.inc"

.import SetPrgData, SetChrBank, PpuAddr, PpuFill, LoadPalette, Random
.import Div8, Div16, Mul8, VBufAlloc, ScreenOff, ScreenOn
.import RowSegs, WriteRowSegs, FillRowSegs, PutNumber, PutString
.import mon_tab, mon_names, item_tab, item_names, tech_tab, tech_names
.import class_tab, class_names, xp_tab, form_tab, zone_tab
.import learn_tab, learn_idx
.import spr_palette

.export BattleEnter, BattleTick, BattleResult, XpAward
.export LearnTechs, Rederive, InitParty, RollEncounter

; battle phases
BP_INTRO   = 0
BP_CMD     = 1
BP_TARGET  = 2
BP_TECHSEL = 3
BP_ITEMSEL = 4
BP_RESOLVE = 5
BP_MSG     = 6
BP_VICTORY = 7
BP_DEFEAT  = 8
BP_FLED    = 9
BP_DONE    = 10

; commands
CMD_FIGHT = 0
CMD_TECH  = 1
CMD_ITEM  = 2
CMD_GUARD = 3
CMD_RUN   = 4

TEXT_ROW0 = 21
MSG_HOLD  = 40              ; frames a battle message stays up on its own

.segment "BANK25"

; =============================================================================
; Entering a battle
; =============================================================================
; A = formation id.
.proc BattleEnter
    sta btl_form
    lda #0
    sta btl_result
    sta ord_i
    sta btl_round
    sta btl_win
    sta btl_win+1
    sta btl_cred
    sta btl_cred+1

    jsr LoadFormation
    lda #SFX_ENCOUNTER
    sta sfx_req
    lda btl_boss
    and #1
    beq :+
    lda #SONG_BOSS
    jmp :++
:   lda #SONG_BATTLE
:   sta music_req
    jsr SetupCombatants
    jsr DrawBattleScreen
    lda #BP_INTRO
    sta btl_phase
    jsr MsgAppeared
    rts
.endproc

; Read the formation record and both monster records.
.proc LoadFormation
    lda #BANK_TABLES
    jsr SetPrgData
    lda btl_form
    sta mul_a
    lda #5
    sta mul_b
    jsr Mul8
    lda mul_res
    clc
    adc #<form_tab
    sta srcp
    lda mul_res+1
    adc #>form_tab
    sta srcp+1
    ldy #0
    lda (srcp),y
    sta btl_type0
    iny
    lda (srcp),y
    sta tmpa                ; count of type 0
    iny
    lda (srcp),y
    sta btl_type1
    iny
    lda (srcp),y
    sta tmpb                ; count of type 1
    iny
    lda (srcp),y
    sta btl_boss

    ; slot assignment
    ldx #0
@t0:
    cpx tmpa
    bcs @t1
    lda #0
    sta btl_slot_type,x
    inx
    cpx #4
    bcc @t0
@t1:
    ldy #0
@t1lp:
    cpy tmpb
    bcs @done
    cpx #4
    bcs @done
    lda #1
    sta btl_slot_type,x
    inx
    iny
    bne @t1lp
@done:
    stx btl_nenemy
    lda btl_type0
    ldx #<mon_rec
    ldy #>mon_rec
    jsr ReadMonster
    lda btl_type1
    ldx #<mon_rec2
    ldy #>mon_rec2
    jsr ReadMonster
    rts
.endproc

; A = monster id, X/Y = destination pointer.
.proc ReadMonster
    stx dstp
    sty dstp+1
    sta mul_a
    lda #MON_REC
    sta mul_b
    jsr Mul8
    lda mul_res
    clc
    adc #<mon_tab
    sta srcp
    lda mul_res+1
    adc #>mon_tab
    sta srcp+1
    ldy #0
:   lda (srcp),y
    sta (dstp),y
    iny
    cpy #MON_REC
    bne :-
    rts
.endproc

; Mirror party stats into the combatant arrays and roll up the enemies.
.proc SetupCombatants
    ldx #0
@party:
    txa
    asl a
    asl a
    asl a
    asl a
    asl a
    tay                     ; y = member * 32
    lda party+c_hp,y
    sta b_hp,x
    lda party+c_hp+1,y
    sta b_hp+8,x
    lda party+c_hpmax,y
    sta b_hpmax,x
    lda party+c_hpmax+1,y
    sta b_hpmax+8,x
    lda party+c_atk,y
    sta b_atk,x
    lda party+c_def,y
    sta b_def,x
    lda party+c_agi,y
    sta b_agi,x
    lda party+c_spi,y
    sta b_spi,x
    lda party+c_status,y
    sta b_status,x
    lda party+c_eva,y
    sta b_evade,x
    lda #0
    sta b_guard,x
    lda party+c_hp,y
    ora party+c_hp+1,y
    beq @dead
    lda party+c_status,y
    and #ST_DOWN
    bne @dead
    lda #1
    sta b_alive,x
    jmp @next
@dead:
    lda #0
    sta b_alive,x
@next:
    inx
    cpx #4
    bcc @party

    ; enemies
    ldx #0
@enemy:
    cpx btl_nenemy
    bcs @clear
    txa
    clc
    adc #4
    tay                     ; combatant index
    lda btl_slot_type,x
    beq @m0
    jsr FillFromRec2
    jmp @nexte
@m0:
    jsr FillFromRec
@nexte:
    inx
    cpx #4
    bcc @enemy
    jmp @fin
@clear:
    txa
    clc
    adc #4
    tay
    lda #0
    sta b_alive,y
    inx
    cpx #4
    bcc @clear
@fin:
    lda #8
    sta n_comb
    rts
.endproc

; Y = combatant index; copy mon_rec into the combatant arrays.
.proc FillFromRec
    lda mon_rec+0
    sta b_hp,y
    sta b_hpmax,y
    lda mon_rec+1
    sta b_hp+8,y
    sta b_hpmax+8,y
    lda mon_rec+2
    sta b_atk,y
    lda mon_rec+3
    sta b_def,y
    lda mon_rec+4
    sta b_agi,y
    lda mon_rec+5
    sta b_spi,y
    lda mon_rec+10
    sta b_elem,y
    lda #0
    sta b_status,y
    sta b_guard,y
    lda #4
    sta b_evade,y
    lda #1
    sta b_alive,y
    lda btl_type0
    sta b_kind,y
    rts
.endproc

.proc FillFromRec2
    lda mon_rec2+0
    sta b_hp,y
    sta b_hpmax,y
    lda mon_rec2+1
    sta b_hp+8,y
    sta b_hpmax+8,y
    lda mon_rec2+2
    sta b_atk,y
    lda mon_rec2+3
    sta b_def,y
    lda mon_rec2+4
    sta b_agi,y
    lda mon_rec2+5
    sta b_spi,y
    lda mon_rec2+10
    sta b_elem,y
    lda #0
    sta b_status,y
    sta b_guard,y
    lda #4
    sta b_evade,y
    lda #1
    sta b_alive,y
    lda btl_type1
    sta b_kind,y
    rts
.endproc

; =============================================================================
; Drawing the arena
; =============================================================================
.proc DrawBattleScreen
    jsr ScreenOff
    ; the battle screen is unscrolled: every window routine then works as-is
    lda #0
    sta cam_x
    sta cam_x+1
    sta cam_y
    sta cam_y+1
    sta cam_tx
    sta cam_ty
    sta scroll_x
    sta scroll_y
    lda ppu_ctrl
    and #%11111110
    sta ppu_ctrl

    ; monster CHR into the two BG banks
    lda #BANK_TABLES
    jsr SetPrgData
    lda btl_type0
    clc
    adc #CHR_MONSTER_BASE
    ldx #SEL_CHR4
    jsr SetChrBank
    lda btl_type1
    clc
    adc #CHR_MONSTER_BASE
    ldx #SEL_CHR5
    jsr SetChrBank

    ; palette: monster type 0 -> sub 0, type 1 -> sub 1, UI -> sub 3
    ldx #0
@pal:
    lda batt_pal,x
    sta pal_buf,x
    inx
    cpx #16
    bne @pal
    ldx #0
@spal:
    lda spr_palette,x
    sta pal_buf+16,x
    inx
    cpx #16
    bne @spal
    lda #<pal_buf
    sta ptr
    lda #>pal_buf
    sta ptr+1
    jsr LoadPalette

    ; clear both nametables and the attribute tables
    lda #$20
    ldx #$00
    jsr PpuAddr
    ldy #16
    lda #$00
@clr:
    ldx #0
    jsr PpuFill
    dey
    bne @clr

    jsr DrawEnemies
    jsr DrawWindowDirect
    jsr DrawHudDirect
    jsr ScreenOn
    rts
.endproc

; Paint every living enemy as a block of background tiles.
.proc DrawEnemies
    ldx #0
@lp:
    cpx btl_nenemy
    bcs @done
    stx loop_i
    txa
    clc
    adc #4
    tay
    lda b_alive,y
    beq @next
    jsr DrawOneEnemy
@next:
    ldx loop_i
    inx
    cpx #4
    bcc @lp
@done:
    rts
.endproc

; X = enemy slot.
.proc DrawOneEnemy
    lda btl_slot_type,x
    sta tmpc                ; type (0/1)
    beq :+
    lda mon_rec2+15
    jmp @size
:   lda mon_rec+15
@size:
    sta tmpd                ; size in tiles (4/6/8)

    ; screen position from a table by slot and size
    lda enemy_x,x
    sta tmpa
    lda enemy_y,x
    sta tmpb
    ; large monsters are pulled left/up so they stay on screen
    lda tmpd
    cmp #4
    beq @pos
    lda tmpa
    sec
    sbc #2
    bpl :+
    lda #0
:   sta tmpa
    lda tmpb
    sec
    sbc #2
    bpl :+
    lda #0
:   sta tmpb
@pos:
    ; base tile index: $80 for type 0, $C0 for type 1
    lda tmpc
    beq :+
    lda #$C0
    jmp :++
:   lda #$80
:   sta loop_j              ; running tile index

    lda #0
    sta sub_i               ; row counter
@row:
    ; PPU address = $2000 + (tmpb + sub_i) * 32 + tmpa
    lda tmpb
    clc
    adc sub_i
    sta tmp0
    lsr a
    lsr a
    lsr a
    clc
    adc #$20
    sta vb_hi
    lda tmp0
    and #7
    asl a
    asl a
    asl a
    asl a
    asl a
    clc
    adc tmpa
    sta vb_lo
    lda vb_hi
    ldx vb_lo
    jsr PpuAddr
    ldx tmpd
@col:
    lda loop_j
    sta PPUDATA
    inc loop_j
    dex
    bne @col
    inc sub_i
    lda sub_i
    cmp tmpd
    bcc @row

    ; attributes: the enemy block takes its type's sub-palette
    lda tmpc
    sta tmp1
    lda tmpa
    lsr a
    lsr a
    sta tmp2                ; attr column
    lda tmpb
    lsr a
    lsr a
    sta tmp3                ; attr row
    lda tmpd
    lsr a
    lsr a
    sta tmp4                ; attr blocks across
    lda #0
    sta sub_j
@arow:
    lda #0
    sta sub_i
@acol:
    lda tmp3
    clc
    adc sub_j
    asl a
    asl a
    asl a
    clc
    adc tmp2
    adc sub_i
    tax
    cpx #64
    bcs @askip
    lda tmp1
    beq @p0
    lda #%01010101
    jmp @sta
@p0:
    lda #%00000000
@sta:
    sta attr_shadow,x
    lda #$23
    ldy #$C0
    sty tmp5
    txa
    clc
    adc tmp5
    tay
    lda #$23
    bcc :+
    lda #$24
:   pha
    tya
    tax
    pla
    jsr PpuAddr
    lda tmp1
    beq @w0
    lda #%01010101
    jmp @w
@w0:
    lda #0
@w: sta PPUDATA
@askip:
    inc sub_i
    lda sub_i
    cmp tmp4
    bcc @acol
    inc sub_j
    lda sub_j
    cmp tmp4
    bcc @arow
    rts
.endproc

; The HUD, written straight to VRAM while rendering is off (four full rows do
; not fit in one vblank through the transfer queue).
.proc DrawHudDirect
    lda #0
    sta loop_i
@lp:
    jsr HudLine
    lda #26
    clc
    adc loop_i
    sta tmp0
    lsr a
    lsr a
    lsr a
    clc
    adc #$20
    sta tmp1
    lda tmp0
    and #7
    asl a
    asl a
    asl a
    asl a
    asl a
    tax
    lda tmp1
    jsr PpuAddr
    ldy #0
:   lda linebuf,y
    sta PPUDATA
    iny
    cpy #32
    bne :-
    inc loop_i
    lda loop_i
    cmp #4
    bcc @lp
    rts
.endproc

; The party HUD: four rows of NAME / HP / TP at the bottom of the screen.
.proc DrawHud
    lda #0
    sta loop_i
@lp:
    jsr HudLine
    lda #26
    clc
    adc loop_i
    jsr RowSegs
    jsr WriteRowSegs
    inc loop_i
    lda loop_i
    cmp #4
    bcc @lp
    rts
.endproc

; Compose HUD line loop_i into linebuf.
.proc HudLine
    ldx #0
    lda #0
:   sta linebuf,x
    inx
    cpx #32
    bne :-
    lda loop_i
    cmp party_n
    bcs @done
    ; name
    lda loop_i
    asl a
    asl a
    asl a
    asl a
    asl a
    tay
    lda party+c_name,y
    jsr NameToPtr
    ldx #1
    jsr PutString
    ; HP
    ldx #10
    lda loop_i
    asl a
    asl a
    asl a
    asl a
    asl a
    tay
    lda party+c_hp,y
    sta num_lo
    lda party+c_hp+1,y
    sta num_hi
    jsr PutNumber
    lda #46                 ; '/' in the font charset
    sta linebuf,x
    inx
    lda loop_i
    asl a
    asl a
    asl a
    asl a
    asl a
    tay
    lda party+c_hpmax,y
    sta num_lo
    lda party+c_hpmax+1,y
    sta num_hi
    jsr PutNumber
    ; TP
    ldx #24
    lda loop_i
    asl a
    asl a
    asl a
    asl a
    asl a
    tay
    lda party+c_tp,y
    sta num_lo
    lda #0
    sta num_hi
    jsr PutNumber
@done:
    rts
.endproc

; A = class index -> ptr points at that class's name (used as the character's).
.proc NameToPtr
    sta mul_a
    lda #NAME_LEN
    sta mul_b
    jsr Mul8
    lda #BANK_TABLES
    jsr SetPrgData
    lda mul_res
    clc
    adc #<class_names
    sta ptr
    lda mul_res+1
    adc #>class_names
    sta ptr+1
    rts
.endproc

; A = monster id -> ptr points at its name.
.proc MonNameToPtr
    sta mul_a
    lda #NAME_LEN
    sta mul_b
    jsr Mul8
    lda #BANK_TABLES
    jsr SetPrgData
    lda mul_res
    clc
    adc #<mon_names
    sta ptr
    lda mul_res+1
    adc #>mon_names
    sta ptr+1
    rts
.endproc

.segment "BANK25"
enemy_x:  .byte 3, 11, 19, 26
enemy_y:  .byte 4, 8, 4, 9
batt_pal:
    .byte $0F,$16,$27,$30
    .byte $0F,$11,$21,$30
    .byte $0F,$09,$19,$29
    .byte $0F,$00,$10,$30

; =============================================================================
; The window: drawn once, directly, while rendering is off
; =============================================================================
F_TL = TILE_FRAME + 0
F_T  = TILE_FRAME + 1
F_TR = TILE_FRAME + 2
F_L  = TILE_FRAME + 3
F_R  = TILE_FRAME + 5
F_BL = TILE_FRAME + 6
F_B  = TILE_FRAME + 7
F_BR = TILE_FRAME + 8

BOX_ROW = 20

.proc DrawWindowDirect
    lda #0
    sta loop_i
@row:
    lda loop_i
    beq @top
    cmp #5
    beq @bot
    lda #F_L
    sta linebuf
    lda #F_R
    sta linebuf+31
    lda #0
    ldx #1
:   sta linebuf,x
    inx
    cpx #31
    bne :-
    jmp @put
@top:
    lda #F_TL
    sta linebuf
    lda #F_TR
    sta linebuf+31
    lda #F_T
    ldx #1
:   sta linebuf,x
    inx
    cpx #31
    bne :-
    jmp @put
@bot:
    lda #F_BL
    sta linebuf
    lda #F_BR
    sta linebuf+31
    lda #F_B
    ldx #1
:   sta linebuf,x
    inx
    cpx #31
    bne :-
@put:
    lda #BOX_ROW
    clc
    adc loop_i
    sta tmp0
    lsr a
    lsr a
    lsr a
    clc
    adc #$20
    sta tmp1
    lda tmp0
    and #7
    asl a
    asl a
    asl a
    asl a
    asl a
    tax
    lda tmp1
    jsr PpuAddr
    ldy #0
:   lda linebuf,y
    sta PPUDATA
    iny
    cpy #32
    bne :-
    inc loop_i
    lda loop_i
    cmp #6
    bcs :+
    jmp @row
    :

    ; window + HUD attributes: rows 20-29 all take sub-palette 3
    lda #$23
    ldx #$E8                ; attribute rows 5-7 ($23C0 + 5*8)
    jsr PpuAddr
    lda #%11111111
    ldx #24
    jsr PpuFill
    rts
.endproc

; =============================================================================
; Line composition helpers
; =============================================================================
.proc BClear
    lda #F_L
    sta linebuf
    lda #F_R
    sta linebuf+31
    lda #0
    ldx #1
:   sta linebuf,x
    inx
    cpx #31
    bne :-
    rts
.endproc

; A = interior line (0..3): write linebuf there.
.proc BPut
    clc
    adc #TEXT_ROW0
    jsr RowSegs
    jmp WriteRowSegs
.endproc

.proc BClearAll
    lda #0
    sta loop_j
@lp:
    jsr BClear
    lda loop_j
    jsr BPut
    inc loop_j
    lda loop_j
    cmp #4
    bcc @lp
    rts
.endproc

; ptr = string, X = column: copy into linebuf.
.proc BStr
    jmp PutString
.endproc

; A = combatant index -> ptr = its name.
.proc CombatantName
    cmp #4
    bcs @enemy
    asl a
    asl a
    asl a
    asl a
    asl a
    tay
    lda party+c_name,y
    jmp NameToPtr
@enemy:
    tay
    lda b_kind,y
    jmp MonNameToPtr
.endproc

; =============================================================================
; Per-frame tick
; =============================================================================
.proc BattleTick
    lda btl_phase
    cmp #BP_DONE
    bcs @done
    asl a
    tax
    lda phase_tab+1,x
    pha
    lda phase_tab,x
    pha
@done:
    rts
.endproc

; --- BP_INTRO ----------------------------------------------------------------
.proc PhIntro
    jsr WaitAdvance
    bcc @done
    lda #0
    sta btl_actor
    jsr StartCommand
@done:
    rts
.endproc

; Wait for A or the hold timer. Carry set when it is time to move on.
.proc WaitAdvance
    lda msg_timer
    beq @ready
    dec msg_timer
    lda pad1_new
    and #BTN_A
    beq @wait
@ready:
    lda #0
    sta msg_timer
    sec
    rts
@wait:
    clc
    rts
.endproc

; --- command entry -----------------------------------------------------------
.proc StartCommand
@find:
    lda btl_actor
    cmp #4
    bcs @allpicked
    ldx btl_actor
    lda b_alive,x
    bne @ask
    lda #$FF
    sta act_cmd,x
    inc btl_actor
    jmp @find
@ask:
    lda #0
    sta menu_cursor
    lda #BP_CMD
    sta btl_phase
    jsr DrawCommandMenu
    rts
@allpicked:
    jsr StartResolve
    rts
.endproc

.proc DrawCommandMenu
    lda #0
    sta list_kind
    lda #$0F
    sta ui_pending
    rts
.endproc

.proc DrawCmdLine0
    jsr BClear
    lda #<s_who
    sta ptr
    lda #>s_who
    sta ptr+1
    ldx #1
    jsr BStr
    lda btl_actor
    jsr CombatantName
    ldx #7
    jsr BStr
    lda #0
    jmp BPut
.endproc

.proc DrawCmdLine1
    jsr BClear
    lda #<s_cmd1
    sta ptr
    lda #>s_cmd1
    sta ptr+1
    ldx #3
    jsr BStr
    lda menu_cursor
    cmp #3
    bcs :+
    ldx menu_cursor
    lda cmd_col,x
    tax
    lda #TILE_CURSOR
    sta linebuf,x
:   lda #1
    jmp BPut
.endproc

.proc DrawCmdLine2
    jsr BClear
    lda #<s_cmd2
    sta ptr
    lda #>s_cmd2
    sta ptr+1
    ldx #3
    jsr BStr
    lda menu_cursor
    cmp #3
    bcc :+
    ldx menu_cursor
    lda cmd_col,x
    tax
    lda #TILE_CURSOR
    sta linebuf,x
:   lda #2
    jmp BPut
.endproc

.proc DrawCmdCursor
    lda #$06                ; only the two option rows change
    ora ui_pending
    sta ui_pending
    rts
.endproc

; --- the UI line pacer -------------------------------------------------------
; Draw at most two pending interior lines per frame. A full 32-tile row costs
; ~480 vblank cycles, so two rows plus the HUD refresh is the safe ceiling.
.proc UiFlush
    ldx #2
@lp:
    lda ui_pending
    beq @done
    ldy #0
@find:
    lda bitmask,y
    and ui_pending
    bne @got
    iny
    cpy #4
    bcc @find
    lda #0
    sta ui_pending
    rts
@got:
    lda bitmask,y
    eor #$FF
    and ui_pending
    sta ui_pending
    tya
    pha
    txa
    pha
    pla
    tax
    pla
    jsr DrawListLine
    dex
    bne @lp
@done:
    rts
.endproc

; A = interior line to compose and write, dispatching on list_kind.
.proc DrawListLine
    sta sub_j
    lda list_kind
    beq @cmd
    cmp #1
    beq @target
    cmp #2
    beq @tech
    lda sub_j
    jmp ItemLine
@cmd:
    lda sub_j
    beq :+
    cmp #1
    beq :++
    cmp #2
    beq :+++
    jsr BClear
    lda #3
    jmp BPut
:   jmp DrawCmdLine0
:   jmp DrawCmdLine1
:   jmp DrawCmdLine2
@target:
    lda sub_j
    jmp TargetLine
@tech:
    lda sub_j
    jmp TechLine
.endproc

.proc PhCmd
    jsr UiFlush
    lda pad1_new
    and #BTN_RIGHT|BTN_DOWN
    beq :+
    inc menu_cursor
    lda menu_cursor
    cmp #5
    bcc @redraw
    lda #0
    sta menu_cursor
    jmp @redraw
:   lda pad1_new
    and #BTN_LEFT|BTN_UP
    beq :+
    dec menu_cursor
    bpl @redraw
    lda #4
    sta menu_cursor
    jmp @redraw
:   lda pad1_new
    and #BTN_A
    bne @choose
    rts
@redraw:
    lda #SFX_CURSOR
    sta sfx_req
    jsr DrawCmdCursor
    rts
@choose:
    lda #SFX_CONFIRM
    sta sfx_req
    ldx btl_actor
    lda menu_cursor
    sta act_cmd,x
    cmp #CMD_FIGHT
    beq @target
    cmp #CMD_TECH
    beq @tech
    cmp #CMD_ITEM
    beq @item
    ; GUARD and RUN need no target
    lda #0
    sta act_tgt,x
    inc btl_actor
    jmp StartCommand
@target:
    jsr StartTarget
    rts
@tech:
    jsr StartTechSel
    rts
@item:
    jsr StartItemSel
    rts
.endproc

; --- target selection --------------------------------------------------------
.proc StartTarget
    ldx #0                  ; start on the first LIVING enemy, never a corpse
@find:
    lda b_alive+4,x
    bne @got
    inx
    cpx #4
    bcc @find
    ldx #0
@got:
    stx sel_i
    lda #0
    lda #BP_TARGET
    sta btl_phase
    jsr DrawTargets
    rts
.endproc

.proc DrawTargets
    lda #1
    sta list_kind
    lda #$0F
    sta ui_pending
    rts
.endproc

; A = line: one enemy row.
.proc TargetLine
    sta sub_i
    jsr BClear
    lda sub_i
    clc
    adc #4
    tay
    lda b_alive,y
    beq @put
    lda sub_i
    cmp sel_i
    bne :+
    lda #TILE_CURSOR
    sta linebuf+2
:   lda sub_i
    clc
    adc #4
    jsr CombatantName
    ldx #4
    jsr BStr
@put:
    lda sub_i
    jmp BPut
.endproc

.proc PhTarget
    jsr UiFlush
    lda pad1_new
    and #BTN_B
    beq :+
    jsr DrawCommandMenu
    lda #BP_CMD
    sta btl_phase
    rts
:   lda pad1_new
    and #BTN_DOWN|BTN_RIGHT
    beq :+
    jsr NextTarget
    jmp @redraw
:   lda pad1_new
    and #BTN_UP|BTN_LEFT
    beq :+
    jsr PrevTarget
    jmp @redraw
:   lda pad1_new
    and #BTN_A
    beq @done
    ldx sel_i
    lda b_alive+4,x
    beq @done
    txa
    clc
    adc #4
    ldx btl_actor
    sta act_tgt,x
    inc btl_actor
    jmp StartCommand
@redraw:
    jsr DrawTargets
@done:
    rts
.endproc

.proc NextTarget
    ldy #4
@lp:
    inc sel_i
    lda sel_i
    cmp #4
    bcc :+
    lda #0
    sta sel_i
:   ldx sel_i
    lda b_alive+4,x
    bne @ok
    dey
    bne @lp
@ok:
    rts
.endproc

.proc PrevTarget
    ldy #4
@lp:
    dec sel_i
    bpl :+
    lda #3
    sta sel_i
:   ldx sel_i
    lda b_alive+4,x
    bne @ok
    dey
    bne @lp
@ok:
    rts
.endproc

; --- tech selection ----------------------------------------------------------
; Build the list of techs the actor knows into tmp_buf.
.proc BuildTechList
    lda btl_actor
    asl a
    asl a
    asl a
    asl a
    asl a
    tay
    lda party+c_psi,y
    sta tmp0
    lda party+c_psi+1,y
    sta tmp1
    lda party+c_bio,y
    sta tmp2
    lda party+c_bio+1,y
    sta tmp3
    ldx #0                  ; output count
    lda #0
    sta loop_j              ; tech index
@lp:
    lda loop_j
    cmp #16
    bcs @bio
    lda loop_j
    cmp #8
    bcs @psihi
    ldy loop_j
    lda tmp0
    jmp @test
@psihi:
    lda loop_j
    sec
    sbc #8
    tay
    lda tmp1
    jmp @test
@bio:
    lda loop_j
    sec
    sbc #16
    cmp #8
    bcs @biohi
    tay
    lda tmp2
    jmp @test
@biohi:
    sec
    sbc #8
    tay
    lda tmp3
@test:
    cpy #0
    beq @have
:   lsr a
    dey
    bne :-
@have:
    and #1
    beq @next
    lda loop_j
    sta tmp_buf,x
    inx
    cpx #16
    bcs @done
@next:
    inc loop_j
    lda loop_j
    cmp #32
    bcc @lp
@done:
    stx sel_max
    rts
.endproc

.proc StartTechSel
    jsr BuildTechList
    lda sel_max
    bne :+
    jsr DrawCommandMenu     ; nothing known: stay on the command menu
    lda #BP_CMD
    sta btl_phase
    rts
:   lda #0
    sta sel_i
    sta sel_top
    lda #BP_TECHSEL
    sta btl_phase
    jsr DrawTechList
    rts
.endproc

.proc DrawTechList
    lda #2
    sta list_kind
    lda #$0F
    sta ui_pending
    rts
.endproc

; A = line: one tech row.
.proc TechLine
    sta sub_i
    jsr BClear
    lda sub_i
    clc
    adc sel_top
    cmp sel_max
    bcs @put
    sta tmp4
    cmp sel_i
    bne :+
    lda #TILE_CURSOR
    sta linebuf+2
:   ldx tmp4
    lda tmp_buf,x
    sta tmp5
    sta mul_a
    lda #NAME_LEN
    sta mul_b
    jsr Mul8
    lda #BANK_TABLES
    jsr SetPrgData
    lda mul_res
    clc
    adc #<tech_names
    sta ptr
    lda mul_res+1
    adc #>tech_names
    sta ptr+1
    ldx #4
    jsr BStr
    lda tmp5
    jsr TechRec
    lda tech_rec+1
    sta num_lo
    lda #0
    sta num_hi
    ldx #20
    jsr PutNumber
@put:
    lda sub_i
    jmp BPut
.endproc

; A = tech id -> tech_rec holds its record.
.proc TechRec
    sta mul_a
    lda #TECH_REC
    sta mul_b
    jsr Mul8
    lda #BANK_TABLES
    jsr SetPrgData
    lda mul_res
    clc
    adc #<tech_tab
    sta srcp
    lda mul_res+1
    adc #>tech_tab
    sta srcp+1
    ldy #0
:   lda (srcp),y
    sta tech_rec,y
    iny
    cpy #TECH_REC
    bne :-
    rts
.endproc

.proc PhTechSel
    jsr UiFlush
    lda pad1_new
    and #BTN_B
    beq :+
    jsr DrawCommandMenu
    lda #BP_CMD
    sta btl_phase
    rts
:   lda pad1_new
    and #BTN_DOWN
    beq :+
    inc sel_i
    lda sel_i
    cmp sel_max
    bcc @scroll
    lda #0
    sta sel_i
    jmp @scroll
:   lda pad1_new
    and #BTN_UP
    beq :+
    dec sel_i
    bpl @scroll
    lda sel_max
    sec
    sbc #1
    sta sel_i
    jmp @scroll
:   lda pad1_new
    and #BTN_A
    beq @done
    ; commit: check TP
    ldx sel_i
    lda tmp_buf,x
    sta tmp5
    jsr TechRec
    lda btl_actor
    asl a
    asl a
    asl a
    asl a
    asl a
    tay
    lda party+c_tp,y
    cmp tech_rec+1
    bcc @done               ; not enough TP: ignore
    ldx btl_actor
    lda tmp5
    sta act_arg,x
    ; targeting: enemy for offensive, self-party for support
    lda tech_rec+4
    cmp #2                  ; TG_ONE_ALLY
    bcs @ally
    jsr StartTarget
    rts
@ally:
    lda #0
    sta act_tgt,x           ; support techs default to the whole party
    inc btl_actor
    jmp StartCommand
@scroll:
    lda sel_i
    cmp sel_top
    bcs :+
    sta sel_top
:   lda sel_i
    sec
    sbc #3
    bcc :+
    cmp sel_top
    bcc :+
    sta sel_top
:   jsr DrawTechList
@done:
    rts
.endproc

; --- item selection ----------------------------------------------------------
.proc StartItemSel
    ldx #0
    ldy #0
@lp:
    lda inv_id,x
    beq @next
    lda inv_ct,x
    beq @next
    lda inv_id,x
    sta tmp_buf,y
    iny
    cpy #16
    bcs @done
@next:
    inx
    cpx #32
    bcc @lp
@done:
    sty sel_max
    tya
    bne :+
    jsr DrawCommandMenu
    lda #BP_CMD
    sta btl_phase
    rts
:   lda #0
    sta sel_i
    sta sel_top
    lda #BP_ITEMSEL
    sta btl_phase
    jsr DrawItemList
    rts
.endproc

.proc DrawItemList
    lda #3
    sta list_kind
    lda #$0F
    sta ui_pending
    rts
.endproc

; A = line: one inventory row.
.proc ItemLine
    sta sub_i
    jsr BClear
    lda sub_i
    clc
    adc sel_top
    cmp sel_max
    bcs @put
    sta tmp4
    cmp sel_i
    bne :+
    lda #TILE_CURSOR
    sta linebuf+2
:   ldx tmp4
    lda tmp_buf,x
    sta mul_a
    lda #NAME_LEN
    sta mul_b
    jsr Mul8
    lda #BANK_TABLES
    jsr SetPrgData
    lda mul_res
    clc
    adc #<item_names
    sta ptr
    lda mul_res+1
    adc #>item_names
    sta ptr+1
    ldx #4
    jsr BStr
@put:
    lda sub_i
    jmp BPut
.endproc

.proc PhItemSel
    jsr UiFlush
    lda pad1_new
    and #BTN_B
    beq :+
    jsr DrawCommandMenu
    lda #BP_CMD
    sta btl_phase
    rts
:   lda pad1_new
    and #BTN_DOWN
    beq :+
    inc sel_i
    lda sel_i
    cmp sel_max
    bcc @scroll
    lda #0
    sta sel_i
    jmp @scroll
:   lda pad1_new
    and #BTN_UP
    beq :+
    dec sel_i
    bpl @scroll
    lda sel_max
    sec
    sbc #1
    sta sel_i
    jmp @scroll
:   lda pad1_new
    and #BTN_A
    beq @done
    ldx sel_i
    lda tmp_buf,x
    ldx btl_actor
    sta act_arg,x
    lda #0
    sta act_tgt,x
    inc btl_actor
    jmp StartCommand
@scroll:
    lda sel_i
    cmp sel_top
    bcs :+
    sta sel_top
:   lda sel_i
    sec
    sbc #3
    bcc :+
    cmp sel_top
    bcc :+
    sta sel_top
:   jsr DrawItemList
@done:
    rts
.endproc

; =============================================================================
; Resolution
; =============================================================================
; Roll initiative for every living combatant and sort descending.
.proc StartResolve
    ldx #0
@roll:
    lda b_alive,x
    beq @dead
    jsr Random
    and #15
    clc
    adc b_agi,x
    bcc :+
    lda #255
:   sta b_init,x
    jmp @next
@dead:
    lda #0
    sta b_init,x
@next:
    inx
    cpx #8
    bcc @roll

    ; selection sort into b_order
    ldx #0
@sel:
    ldy #0
    lda #0
    sta tmp0                ; best value
    sta tmp1                ; best index
@scan:
    lda b_init,y
    cmp tmp0
    bcc :+
    beq :+
    sta tmp0
    sty tmp1
:   iny
    cpy #8
    bcc @scan
    lda tmp1
    sta b_order,x
    ldy tmp1
    lda #0
    sta b_init,y
    inx
    cpx #8
    bcc @sel

    lda #0
    sta ord_i
    inc btl_round
    lda #BP_RESOLVE
    sta btl_phase
    rts
.endproc

.proc PhResolve
    jsr CheckEnd
    lda btl_phase
    cmp #BP_RESOLVE
    beq :+
    rts
:   lda ord_i
    cmp #8
    bcc @act
    ; round over: back to command entry
    lda #0
    sta btl_actor
    ldx #0
:   lda #0
    sta b_guard,x
    inx
    cpx #8
    bcc :-
    jmp StartCommand
@act:
    ldx ord_i
    lda b_order,x
    sta btl_actor
    inc ord_i
    tax
    lda b_alive,x
    beq PhResolve           ; skip the dead
    lda b_status,x
    and #ST_STUN
    beq :+
    lda #0
    sta b_status,x          ; stun wears off, turn is lost
    jmp PhResolve
:   lda btl_actor
    cmp #4
    bcs @enemy
    jmp PartyAction
@enemy:
    jmp EnemyAction
.endproc

; --- party actions -----------------------------------------------------------
.proc PartyAction
    ldx btl_actor
    lda act_cmd,x
    cmp #CMD_GUARD
    beq @guard
    cmp #CMD_RUN
    beq @run
    cmp #CMD_TECH
    beq @tech
    cmp #CMD_ITEM
    beq @item
    ; FIGHT
    lda act_tgt,x
    sta btl_target
    tay
    lda b_alive,y
    bne :+
    jsr PickLiveEnemy
    sta btl_target
    bcs :+
    jmp PhResolve           ; nothing left to hit
:   jsr PhysicalAttack
    rts
@guard:
    lda #1
    sta b_guard,x
    lda #<s_guards
    jmp MsgActor
@run:
    jsr TryRun
    rts
@tech:
    jsr CastTech
    rts
@item:
    jsr UseItem
    rts
.endproc

; Physical attack: btl_actor -> btl_target.
.proc PhysicalAttack
    ldx btl_actor
    ldy btl_target
    ; hit chance: 168 - evade, clamped 40..99
    lda #168
    sec
    sbc b_evade,y
    bcs :+
    lda #40
:   cmp #100
    bcc :+
    lda #99
:   cmp #40
    bcs :+
    lda #40
:   sta tmp2
    jsr Random
    sta div_n
    lda #100
    sta div_d
    jsr Div8
    lda div_r
    cmp tmp2
    bcc @hit
    lda #<s_misses
    jmp MsgActorTarget
@hit:
    ; base = atk - def/2, at least 1
    ldx btl_actor
    lda b_atk,x
    sta tmp0
    ldy btl_target
    lda b_def,y
    lsr a
    sta tmp1
    lda tmp0
    sec
    sbc tmp1
    bcs :+
    lda #1
:   bne :+
    lda #1
:   sta tmp0
    ; spread: +-12%, and a 1/32 critical for double
    jsr Random
    and #7
    sec
    sbc #4
    clc
    adc #32
    sta mul_b               ; 28..35
    lda tmp0
    sta mul_a
    jsr Mul8
    lda mul_res
    sta div_n
    lda mul_res+1
    sta div_n+1
    lda #32
    sta div_d
    jsr Div16
    lda div_q
    sta dmg_lo
    lda div_q+1
    sta dmg_hi
    ora dmg_lo
    bne :+
    lda #1
    sta dmg_lo
:   lda #SFX_HIT
    sta sfx_req
    jsr Random
    and #31
    bne @nocrit
    asl dmg_lo
    rol dmg_hi
    lda #SFX_CRIT
    sta sfx_req
@nocrit:
    ldy btl_target
    lda b_guard,y
    beq :+
    lsr dmg_hi
    ror dmg_lo
:   jsr ApplyDamage
    lda #<s_hits
    jsr MsgActorTargetDmg
    rts
.endproc

; Subtract dmg from combatant btl_target, clamping at zero and killing it.
.proc ApplyDamage
    ldy btl_target
    lda b_hp,y
    sec
    sbc dmg_lo
    sta b_hp,y
    lda b_hp+8,y
    sbc dmg_hi
    sta b_hp+8,y
    bcs @alive
    lda #0
    sta b_hp,y
    sta b_hp+8,y
@alive:
    lda b_hp,y
    ora b_hp+8,y
    bne @done
    lda #0
    sta b_alive,y
    cpy #4
    bcs @enemydead
    lda b_status,y
    ora #ST_DOWN
    sta b_status,y
    jmp @done
@enemydead:
    jsr EraseEnemy
@done:
    rts
.endproc

; Blank the tiles of the dead enemy in slot (btl_target - 4).
.proc EraseEnemy
    tya
    sec
    sbc #4
    tax
    stx loop_i
    lda btl_slot_type,x
    beq :+
    lda mon_rec2+15
    jmp :++
:   lda mon_rec+15
:   sta tmpd
    ldx loop_i
    lda enemy_x,x
    sta tmpa
    lda enemy_y,x
    sta tmpb
    lda tmpd
    cmp #4
    beq @go
    lda tmpa
    sec
    sbc #2
    bpl :+
    lda #0
:   sta tmpa
    lda tmpb
    sec
    sbc #2
    bpl :+
    lda #0
:   sta tmpb
@go:
    lda #0
    sta sub_i
@row:
    lda tmpb
    clc
    adc sub_i
    sta tmp0
    lsr a
    lsr a
    lsr a
    clc
    adc #$20
    sta vb_hi
    lda tmp0
    and #7
    asl a
    asl a
    asl a
    asl a
    asl a
    clc
    adc tmpa
    sta vb_lo
    lda #3                  ; fill packet
    sta vb_mode
    lda tmpd
    sta vb_cnt
    jsr VBufAlloc
    bcs @next
    ldy #0
    lda #0
    sta (vb_dat),y
@next:
    inc sub_i
    lda sub_i
    cmp tmpd
    bcc @row
    rts
.endproc

; --- enemy actions -----------------------------------------------------------
.proc EnemyAction
    jsr PickLivePartyMember
    bcs :+
    rts
:   sta btl_target
    jsr PhysicalAttack
    rts
.endproc

; -> A = a living party member, carry set if one exists.
.proc PickLivePartyMember
    ldy #8
@try:
    jsr Random
    and #3
    tax
    lda b_alive,x
    bne @ok
    dey
    bne @try
    ; fall back to a scan
    ldx #0
@scan:
    lda b_alive,x
    bne @ok
    inx
    cpx #4
    bcc @scan
    clc
    rts
@ok:
    txa
    sec
    rts
.endproc

; -> A = a living enemy combatant index, carry set if one exists.
.proc PickLiveEnemy
    ldx #4
@scan:
    lda b_alive,x
    bne @ok
    inx
    cpx #8
    bcc @scan
    clc
    rts
@ok:
    txa
    sec
    rts
.endproc

; --- run ---------------------------------------------------------------------
.proc TryRun
    lda btl_boss
    and #1
    beq :+
    lda #<s_norun
    jmp MsgPlain
:   jsr Random
    cmp #96
    bcs @fail
    lda #1
    sta btl_result          ; 1 = fled
    lda #BP_FLED
    sta btl_phase
    lda #<s_ranaway
    jmp MsgPlainPhase
@fail:
    lda #<s_ranfail
    jmp MsgPlain
.endproc

; --- techs -------------------------------------------------------------------
.proc CastTech
    ldx btl_actor
    lda act_arg,x
    sta tmp5
    jsr TechRec
    ; spend TP
    lda btl_actor
    asl a
    asl a
    asl a
    asl a
    asl a
    tay
    lda party+c_tp,y
    sec
    sbc tech_rec+1
    bcs :+
    lda #0
:   sta party+c_tp,y
    lda tech_rec+4          ; target kind
    cmp #2
    bcs @support
    ; offensive: power + spi/2, minus target spi/4
    lda tech_rec+2
    sta tmp0
    ldx btl_actor
    lda b_spi,x
    lsr a
    clc
    adc tmp0
    sta dmg_lo
    lda #0
    sta dmg_hi
    lda tech_rec+4
    cmp #1                  ; TG_ALL_ENEMY
    beq @all
    ldx btl_actor
    lda act_tgt,x
    sta btl_target
    jsr TechDamageOne
    lda #<s_techhit
    jsr MsgActorTargetDmg
    rts
@all:
    lda dmg_lo
    sta tmp6
    ldx #4
@alllp:
    stx loop_i
    lda b_alive,x
    beq @allnext
    stx btl_target
    lda tmp6
    sta dmg_lo
    lda #0
    sta dmg_hi
    jsr TechDamageOne
@allnext:
    ldx loop_i
    inx
    cpx #8
    bcc @alllp
    lda #<s_techall
    jmp MsgActor
@support:
    ; healing: restore power HP to the whole party
    lda tech_rec+2
    beq @nofx
    sta tmp0
    ldx #0
@heal:
    lda b_alive,x
    beq @healnext
    stx loop_i
    jsr HealCombatant
    ldx loop_i
@healnext:
    inx
    cpx #4
    bcc @heal
    lda #<s_healed
    jmp MsgActor
@nofx:
    lda #<s_noeffect
    jmp MsgActor
.endproc

; dmg_lo/hi = raw power; apply resistance and element, then damage btl_target.
.proc TechDamageOne
    ldy btl_target
    lda b_spi,y
    lsr a
    lsr a
    sta tmp1
    lda dmg_lo
    sec
    sbc tmp1
    bcs :+
    lda #1
:   sta dmg_lo
    lda #0
    sta dmg_hi
    ; element: weakness doubles, immunity zeroes
    ldy btl_target
    lda tech_rec+3
    beq @apply
    cmp b_elem,y
    bne @apply
    asl dmg_lo
    rol dmg_hi
@apply:
    jmp ApplyDamage
.endproc

; X = combatant, tmp0 = amount.
.proc HealCombatant
    lda b_hp,x
    clc
    adc tmp0
    sta b_hp,x
    lda b_hp+8,x
    adc #0
    sta b_hp+8,x
    lda b_hp+8,x
    cmp b_hpmax+8,x
    bcc @done
    bne @clamp
    lda b_hp,x
    cmp b_hpmax,x
    bcc @done
@clamp:
    lda b_hpmax,x
    sta b_hp,x
    lda b_hpmax+8,x
    sta b_hp+8,x
@done:
    rts
.endproc

; --- items -------------------------------------------------------------------
.proc UseItem
    ldx btl_actor
    lda act_arg,x
    sta tmp5
    ; find and consume it
    ldx #0
@find:
    lda inv_id,x
    cmp tmp5
    beq @got
    inx
    cpx #32
    bcc @find
    lda #<s_noeffect
    jmp MsgActor
@got:
    dec inv_ct,x
    bne :+
    lda #0
    sta inv_id,x
:   lda tmp5
    sta mul_a
    lda #ITEM_REC
    sta mul_b
    jsr Mul8
    lda #BANK_TABLES
    jsr SetPrgData
    lda mul_res
    clc
    adc #<item_tab
    sta srcp
    lda mul_res+1
    adc #>item_tab
    sta srcp+1
    ldy #6
    lda (srcp),y
    sta tmp2                ; effect
    ldy #1
    lda (srcp),y
    sta tmp0                ; power
    lda tmp2
    cmp #1
    beq @heal
    cmp #5
    beq @bomb
    lda #<s_noeffect
    jmp MsgActor
@heal:
    ldx btl_actor
    jsr HealCombatant
    lda #<s_healed
    jmp MsgActor
@bomb:
    lda tmp0
    sta tmp6
    ldx #4
@lp:
    stx loop_i
    lda b_alive,x
    beq @next
    stx btl_target
    lda tmp6
    sta dmg_lo
    lda #0
    sta dmg_hi
    jsr ApplyDamage
@next:
    ldx loop_i
    inx
    cpx #8
    bcc @lp
    lda #<s_techall
    jmp MsgActor
.endproc

; =============================================================================
; End of battle
; =============================================================================
.proc CheckEnd
    ldx #4
    ldy #0
@enemies:
    lda b_alive,x
    beq :+
    iny
:   inx
    cpx #8
    bcc @enemies
    cpy #0
    bne @party
    jsr StartVictory
    rts
@party:
    ldx #0
    ldy #0
@pl:
    lda b_alive,x
    beq :+
    iny
:   inx
    cpx #4
    bcc @pl
    cpy #0
    bne @done
    lda #2
    sta btl_result
    lda #BP_DEFEAT
    sta btl_phase
    lda #<s_wiped
    jsr MsgPlainPhase
@done:
    rts
.endproc

.proc StartVictory
    ; total XP and credits from every enemy slot
    lda #0
    sta btl_win
    sta btl_win+1
    sta btl_cred
    sta btl_cred+1
    ldx #0
@lp:
    cpx btl_nenemy
    bcs @done
    stx loop_i
    lda btl_slot_type,x
    beq @m0
    lda mon_rec2+6
    sta tmp0
    lda mon_rec2+7
    sta tmp1
    lda mon_rec2+8
    sta tmp2
    lda mon_rec2+9
    sta tmp3
    jmp @add
@m0:
    lda mon_rec+6
    sta tmp0
    lda mon_rec+7
    sta tmp1
    lda mon_rec+8
    sta tmp2
    lda mon_rec+9
    sta tmp3
@add:
    lda btl_win
    clc
    adc tmp0
    sta btl_win
    lda btl_win+1
    adc tmp1
    sta btl_win+1
    lda btl_cred
    clc
    adc tmp2
    sta btl_cred
    lda btl_cred+1
    adc tmp3
    sta btl_cred+1
    ldx loop_i
    inx
    cpx #4
    bcc @lp
@done:
    lda #3
    sta btl_result
    lda #SONG_VICTORY
    sta music_req
    lda #BP_VICTORY
    sta btl_phase
    jsr WriteBackHp
    jsr AwardAll
    jsr MsgVictory
    rts
.endproc

; Copy battle HP/status back into the save-file party records.
.proc WriteBackHp
    ldx #0
@lp:
    txa
    asl a
    asl a
    asl a
    asl a
    asl a
    tay
    lda b_hp,x
    sta party+c_hp,y
    lda b_hp+8,x
    sta party+c_hp+1,y
    lda b_status,x
    sta party+c_status,y
    inx
    cpx #4
    bcc @lp
    rts
.endproc

; Give XP and credits to every living member, then level them up.
.proc AwardAll
    ; credits are shared
    lda credits
    clc
    adc btl_cred
    sta credits
    lda credits+1
    adc btl_cred+1
    sta credits+1
    lda credits+2
    adc #0
    sta credits+2

    ldx #0
@lp:
    stx lvl_i
    lda b_alive,x
    beq @next
    txa
    asl a
    asl a
    asl a
    asl a
    asl a
    tay
    lda party+c_xp,y
    clc
    adc btl_win
    sta party+c_xp,y
    lda party+c_xp+1,y
    adc btl_win+1
    sta party+c_xp+1,y
    lda party+c_xp+2,y
    adc #0
    sta party+c_xp+2,y
    lda lvl_i
    jsr XpAward
@next:
    ldx lvl_i
    inx
    cpx #4
    bcc @lp
    rts
.endproc

; A = party member: level them up while their XP allows it.
.proc XpAward
    sta tmp7
@again:
    lda tmp7
    asl a
    asl a
    asl a
    asl a
    asl a
    tay
    lda party+c_level,y
    cmp #30
    bcs @done
    ; xp_tab[level] is the XP needed to reach level+1
    sta mul_a
    lda #3
    sta mul_b
    jsr Mul8
    lda #BANK_TABLES
    jsr SetPrgData
    lda mul_res
    clc
    adc #<xp_tab
    sta srcp
    lda mul_res+1
    adc #>xp_tab
    sta srcp+1
    lda tmp7
    asl a
    asl a
    asl a
    asl a
    asl a
    tay
    ldx #0
    ; compare 24-bit xp against the requirement
    lda party+c_xp+2,y
    sta tmp0
    lda party+c_xp+1,y
    sta tmp1
    lda party+c_xp,y
    sta tmp2
    ldy #2
    lda (srcp),y
    cmp tmp0
    bcc @levelup
    bne @done
    ldy #1
    lda (srcp),y
    cmp tmp1
    bcc @levelup
    bne @done
    ldy #0
    lda (srcp),y
    cmp tmp2
    bcc @levelup
    beq @levelup
    jmp @done
@levelup:
    jsr LevelUp
    jmp @again
@done:
    rts
.endproc

; tmp7 = party member: apply one level's growth.
.proc LevelUp
    lda tmp7
    asl a
    asl a
    asl a
    asl a
    asl a
    tax
    stx tmp3                ; member offset
    inc party+c_level,x     ; INC has no absolute,Y mode
    tay
    lda party+c_class,y
    sta mul_a
    lda #CLASS_REC
    sta mul_b
    jsr Mul8
    lda #BANK_TABLES
    jsr SetPrgData
    lda mul_res
    clc
    adc #<class_tab
    sta srcp
    lda mul_res+1
    adc #>class_tab
    sta srcp+1
    ; HP
    ldy #6
    lda (srcp),y
    sta tmp0
    ldy tmp3
    lda party+c_hpmax,y
    clc
    adc tmp0
    sta party+c_hpmax,y
    lda party+c_hpmax+1,y
    adc #0
    sta party+c_hpmax+1,y
    lda party+c_hp,y
    clc
    adc tmp0
    sta party+c_hp,y
    lda party+c_hp+1,y
    adc #0
    sta party+c_hp+1,y
    ; TP
    ldy #7
    lda (srcp),y
    sta tmp0
    ldy tmp3
    lda party+c_tpmax,y
    clc
    adc tmp0
    sta party+c_tpmax,y
    lda party+c_tp,y
    clc
    adc tmp0
    sta party+c_tp,y
    ; STR / AGI / VIT / SPI
    ldy #8
    lda (srcp),y
    ldy tmp3
    clc
    adc party+c_str,y
    sta party+c_str,y
    ldy #9
    lda (srcp),y
    ldy tmp3
    clc
    adc party+c_agi,y
    sta party+c_agi,y
    ldy #10
    lda (srcp),y
    ldy tmp3
    clc
    adc party+c_vit,y
    sta party+c_vit,y
    ldy #11
    lda (srcp),y
    ldy tmp3
    clc
    adc party+c_spi,y
    sta party+c_spi,y
    lda tmp7
    jsr LearnTechs
    lda tmp7
    jmp Rederive
.endproc

; A = party member: grant every tech whose level has been reached.
.proc LearnTechs
    asl a
    asl a
    asl a
    asl a
    asl a
    sta tmp3
    tay
    lda party+c_class,y
    asl a
    tax
    lda #BANK_TABLES
    jsr SetPrgData
    lda learn_idx,x
    sta srcp
    lda learn_idx+1,x
    sta srcp+1
    ldy #0
@lp:
    lda (srcp),y
    cmp #$FF
    beq @done
    sta tmp0                ; level
    iny
    lda (srcp),y
    sta tmp1                ; tech index
    iny
    ldx tmp3
    lda party+c_level,x
    cmp tmp0
    bcc @lp
    ; set the bit for tech tmp1
    lda tmp1
    cmp #16
    bcs @bio
    tax
    lda tmp1
    cmp #8
    bcs @psihi
    lda #1
    cpx #0
    beq :+
:   ldx tmp1
    lda bitmask,x
    ldx tmp3
    ora party+c_psi,x
    sta party+c_psi,x
    jmp @lp
@psihi:
    lda tmp1
    sec
    sbc #8
    tax
    lda bitmask,x
    ldx tmp3
    ora party+c_psi+1,x
    sta party+c_psi+1,x
    jmp @lp
@bio:
    lda tmp1
    sec
    sbc #16
    cmp #8
    bcs @biohi
    tax
    lda bitmask,x
    ldx tmp3
    ora party+c_bio,x
    sta party+c_bio,x
    jmp @lp
@biohi:
    sec
    sbc #8
    tax
    lda bitmask,x
    ldx tmp3
    ora party+c_bio+1,x
    sta party+c_bio+1,x
    jmp @lp
@done:
    rts
.endproc

; A = party member: recompute ATK / DEF / EVA from stats and equipment.
.proc Rederive
    asl a
    asl a
    asl a
    asl a
    asl a
    sta tmp3
    tay
    lda party+c_str,y
    lsr a
    sta tmp0
    lda party+c_weapon,y
    jsr ItemPower
    clc
    adc tmp0
    ldy tmp3
    sta party+c_atk,y
    ; DEF
    lda party+c_vit,y
    lsr a
    lsr a
    sta tmp0
    lda party+c_armour,y
    jsr ItemPower
    clc
    adc tmp0
    sta tmp0
    ldy tmp3
    lda party+c_shield,y
    jsr ItemPower
    clc
    adc tmp0
    sta tmp0
    ldy tmp3
    lda party+c_helm,y
    jsr ItemPower
    clc
    adc tmp0
    ldy tmp3
    sta party+c_def,y
    ; EVA
    lda party+c_agi,y
    lsr a
    sta party+c_eva,y
    rts
.endproc

; A = item id -> A = its power byte.
.proc ItemPower
    sta mul_a
    lda #ITEM_REC
    sta mul_b
    jsr Mul8
    lda #BANK_TABLES
    jsr SetPrgData
    lda mul_res
    clc
    adc #<item_tab
    sta srcp
    lda mul_res+1
    adc #>item_tab
    sta srcp+1
    ldy #1
    lda (srcp),y
    rts
.endproc

.proc PhVictory
    jsr WaitAdvance
    bcc @done
    lda #BP_DONE
    sta btl_phase
@done:
    rts
.endproc

.proc PhDefeat
    jsr WaitAdvance
    bcc @done
    lda #BP_DONE
    sta btl_phase
@done:
    rts
.endproc

.proc PhFled
    jsr WaitAdvance
    bcc @done
    jsr WriteBackHp
    lda #BP_DONE
    sta btl_phase
@done:
    rts
.endproc

.proc PhMsg
    jsr WaitAdvance
    bcc @done
    lda #BP_RESOLVE
    sta btl_phase
    jsr DrawHudRows
@done:
    rts
.endproc

.proc DrawHudRows
    lda btl_round
    and #3
    sta loop_i
    jsr HudLine
    lda #26
    clc
    adc loop_i
    jsr RowSegs
    jmp WriteRowSegs
.endproc

.proc BattleResult
    lda btl_result
    rts
.endproc

; =============================================================================
; Battle messages
; =============================================================================
.proc MsgAppeared
    jsr BClearAll
    jsr BClear
    lda btl_type0
    jsr MonNameToPtr
    ldx #1
    jsr BStr
    lda #<s_appears
    sta ptr
    lda #>s_appears
    sta ptr+1
    ldx #14
    jsr BStr
    lda #0
    jsr BPut
    lda #MSG_HOLD
    sta msg_timer
    rts
.endproc

.proc MsgVictory
    jsr BClearAll
    jsr BClear
    lda #<s_victory
    sta ptr
    lda #>s_victory
    sta ptr+1
    ldx #1
    jsr BStr
    lda #0
    jsr BPut
    jsr BClear
    lda btl_win
    sta num_lo
    lda btl_win+1
    sta num_hi
    ldx #2
    jsr PutNumber
    lda #<s_xp
    sta ptr
    lda #>s_xp
    sta ptr+1
    jsr BStr
    lda #1
    jsr BPut
    jsr BClear
    lda btl_cred
    sta num_lo
    lda btl_cred+1
    sta num_hi
    ldx #2
    jsr PutNumber
    lda #<s_cred
    sta ptr
    lda #>s_cred
    sta ptr+1
    jsr BStr
    lda #2
    jsr BPut
    lda #MSG_HOLD*2
    sta msg_timer
    rts
.endproc

; A = low byte of a string address in this bank; show "<actor> <string>".
.proc MsgActor
    sta tmpc
    jsr BClearAll
    jsr BClear
    lda btl_actor
    jsr CombatantName
    ldx #1
    jsr BStr
    lda tmpc
    sta ptr
    lda #>s_hits
    sta ptr+1
    ldx #14
    jsr BStr
    lda #0
    jsr BPut
    jsr EndMsg
    rts
.endproc

.proc MsgActorTarget
    sta tmpc
    jsr BClearAll
    jsr BClear
    lda btl_actor
    jsr CombatantName
    ldx #1
    jsr BStr
    lda tmpc
    sta ptr
    lda #>s_hits
    sta ptr+1
    ldx #14
    jsr BStr
    lda #0
    jsr BPut
    jsr BClear
    lda btl_target
    jsr CombatantName
    ldx #4
    jsr BStr
    lda #1
    jsr BPut
    jsr EndMsg
    rts
.endproc

.proc MsgActorTargetDmg
    sta tmpc
    jsr BClearAll
    jsr BClear
    lda btl_actor
    jsr CombatantName
    ldx #1
    jsr BStr
    lda tmpc
    sta ptr
    lda #>s_hits
    sta ptr+1
    ldx #14
    jsr BStr
    lda #0
    jsr BPut
    jsr BClear
    lda btl_target
    jsr CombatantName
    ldx #2
    jsr BStr
    lda #<s_for
    sta ptr
    lda #>s_for
    sta ptr+1
    ldx #16
    jsr BStr
    lda dmg_lo
    sta num_lo
    lda dmg_hi
    sta num_hi
    ldx #21
    jsr PutNumber
    lda #1
    jsr BPut
    jsr EndMsg
    rts
.endproc

.proc MsgPlain
    sta tmpc
    jsr BClearAll
    jsr BClear
    lda tmpc
    sta ptr
    lda #>s_hits
    sta ptr+1
    ldx #1
    jsr BStr
    lda #0
    jsr BPut
    jsr EndMsg
    rts
.endproc

; As MsgPlain but leaves btl_phase alone (used for terminal messages).
.proc MsgPlainPhase
    sta tmpc
    jsr BClearAll
    jsr BClear
    lda tmpc
    sta ptr
    lda #>s_hits
    sta ptr+1
    ldx #1
    jsr BStr
    lda #0
    jsr BPut
    lda #MSG_HOLD
    sta msg_timer
    rts
.endproc

.proc EndMsg
    lda #MSG_HOLD
    sta msg_timer
    lda #BP_MSG
    sta btl_phase
    rts
.endproc

.segment "BANK25"
phase_tab:
    .addr PhIntro-1
    .addr PhCmd-1
    .addr PhTarget-1
    .addr PhTechSel-1
    .addr PhItemSel-1
    .addr PhResolve-1
    .addr PhMsg-1
    .addr PhVictory-1
    .addr PhDefeat-1
    .addr PhFled-1

cmd_row:  .byte 1, 1, 1, 2, 2
cmd_col:  .byte 1, 9, 17, 1, 9
bitmask:  .byte 1, 2, 4, 8, 16, 32, 64, 128

s_hits:     .byte "ATTACKS!", STR_END
s_misses:   .byte "MISSES.", STR_END
s_guards:   .byte "GUARDS.", STR_END
s_techhit:  .byte "USES A TECH!", STR_END
s_techall:  .byte "STRIKES ALL!", STR_END
s_healed:   .byte "MENDS THE PARTY.", STR_END
s_noeffect: .byte "NO EFFECT.", STR_END
s_appears:  .byte "APPEARS!", STR_END
s_victory:  .byte "THE PARTY IS VICTORIOUS!", STR_END
s_xp:       .byte " XP", STR_END
s_cred:     .byte " CREDITS", STR_END
s_wiped:    .byte "THE PARTY HAS FALLEN.", STR_END
s_ranaway:  .byte "THE PARTY GETS AWAY.", STR_END
s_ranfail:  .byte "NO WAY OUT!", STR_END
s_norun:    .byte "THERE IS NO ESCAPE.", STR_END
s_for:      .byte "FOR", STR_END
s_who:      .byte "TURN:", STR_END
s_cmd1:     .byte "FIGHT   TECH    ITEM", STR_END
s_cmd2:     .byte "GUARD   RUN", STR_END


; =============================================================================
; New game: build the starting party
; =============================================================================
.proc InitParty
    lda #4
    sta party_n
    lda #0
    sta lvl_i
@lp:
    lda lvl_i
    asl a
    asl a
    asl a
    asl a
    asl a
    sta tmp3
    tax
    ; zero the record
    ldy #0
    lda #0
:   sta party,x
    inx
    iny
    cpy #PARTY_SIZE
    bne :-
    ldx tmp3
    lda lvl_i               ; class = slot (SOLDIER RANGER MEDIC PSION)
    sta party+c_class,x
    sta party+c_name,x
    lda #1
    sta party+c_level,x
    ; base stats from the class table
    lda lvl_i
    sta mul_a
    lda #CLASS_REC
    sta mul_b
    jsr Mul8
    lda #BANK_TABLES
    jsr SetPrgData
    lda mul_res
    clc
    adc #<class_tab
    sta srcp
    lda mul_res+1
    adc #>class_tab
    sta srcp+1
    ldx tmp3
    ldy #0
    lda (srcp),y
    sta party+c_hp,x
    sta party+c_hpmax,x
    lda #0
    sta party+c_hp+1,x
    sta party+c_hpmax+1,x
    ldy #1
    lda (srcp),y
    sta party+c_tp,x
    sta party+c_tpmax,x
    ldy #2
    lda (srcp),y
    sta party+c_str,x
    ldy #3
    lda (srcp),y
    sta party+c_agi,x
    ldy #4
    lda (srcp),y
    sta party+c_vit,x
    ldy #5
    lda (srcp),y
    sta party+c_spi,x
    lda #IT_KNIFE
    sta party+c_weapon,x
    lda #IT_WORKSUIT
    sta party+c_armour,x
    lda lvl_i
    jsr LearnTechs
    lda lvl_i
    jsr Rederive
    inc lvl_i
    lda lvl_i
    cmp #4
    bcs :+
    jmp @lp
:
    ; inventory and money
    ldx #0
    lda #0
:   sta inv_id,x
    sta inv_ct,x
    inx
    cpx #32
    bne :-
    lda #IT_MEDKIT
    sta inv_id+0
    lda #5
    sta inv_ct+0
    lda #IT_ANTITOX
    sta inv_id+1
    lda #2
    sta inv_ct+1
.ifdef TEST_NO_CREDITS
    lda #0                      ; test build: a party that cannot afford an inn
.else
    lda #200
.endif
    sta credits
    lda #0
    sta credits+1
    sta credits+2
    ldx #0
    lda #0
:   sta story_flags,x
    inx
    cpx #32
    bne :-
    ldx #0
:   sta chest_flags,x
    inx
    cpx #64
    bne :-
    sta vehicles
    rts
.endproc

; =============================================================================
; Rolling a random encounter for the party's current cell
; =============================================================================
; -> A = formation id, carry set if an encounter should happen.
.proc RollEncounter
    lda enc_tab
    cmp #$FF
    beq @none
    sta tmp0                ; default zone
    lda map_zones+1
    beq @havezone
    ; zone grid: index = (gy/16)*8 + (gx/16)
    lda map_zones
    sta srcp
    lda map_zones+1
    sta srcp+1
    lda map_bank
    jsr SetPrgData
    lda ent_gy
    lsr a
    lsr a
    lsr a
    lsr a
    asl a
    asl a
    asl a
    sta tmp1
    lda ent_gx
    lsr a
    lsr a
    lsr a
    lsr a
    clc
    adc tmp1
    tay
    lda (srcp),y
    sta tmp0
@havezone:
    lda #BANK_TABLES
    jsr SetPrgData
    lda tmp0
    sta mul_a
    lda #8
    sta mul_b
    jsr Mul8
    jsr Random
    and #7
    clc
    adc mul_res
    sta tmp1
    lda mul_res+1
    adc #0
    sta tmp2
    lda tmp1
    clc
    adc #<zone_tab
    sta srcp
    lda tmp2
    adc #>zone_tab
    sta srcp+1
    ldy #0
    lda (srcp),y
    sec
    rts
@none:
    clc
    rts
.endproc
