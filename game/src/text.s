; text.s — windows, text and menus, drawn IN PLACE over the scrolled map and
; restored underneath on close (no rendering-off, no black flash).
; Lives in PRG bank 30 ($C000).
;
; The window is 32 tiles wide and 6 rows tall at screen rows 20-25: a top
; border, four 30-character text lines, a bottom border. It is only ever opened
; while the party leader is grid-aligned, so the camera sits on a 16px boundary
; and the window covers whole attribute quadrants.

.include "nes.inc"
.include "zp.inc"
.include "ram.inc"
.include "banks.inc"
.include "gen/charmap.inc"

.import SetPrgData, VBufAlloc, Div8, Div16
.import RowSlot, DecodeRow, BuildRowStrip, AttrRowShadow, QueueAttrRow
.import AttrRowForce

.export SetMessage, OpenBox, CloseBox, BoxStep, RenderLine, RowSegs
.export WriteRowSegs, FillRowSegs, RenderMenuLine
.export DrawPrompt, ClearPrompt, PutNumber, PutString

BOX_ROW    = 20             ; screen row of the top border
BOX_H      = 6
TEXT_ROW0  = 21             ; first interior line
TEXT_LINES = 4
TEXT_W     = 30

F_TL = TILE_FRAME + 0
F_T  = TILE_FRAME + 1
F_TR = TILE_FRAME + 2
F_L  = TILE_FRAME + 3
F_C  = TILE_FRAME + 4
F_R  = TILE_FRAME + 5
F_BL = TILE_FRAME + 6
F_B  = TILE_FRAME + 7
F_BR = TILE_FRAME + 8

.segment "ENGINE"

; =============================================================================
; Row addressing: one full-width screen row, split across the two nametables
; =============================================================================
; A = screen row (0..29).
.proc RowSegs
    clc
    adc cam_ty
    jsr RowSlot
    sta nt_slot
    lda cam_tx
    and #63
    cmp #32
    bcs @nt1
    sta tmpa
    lda #$20
    sta seg_base
    lda #$24
    sta seg2_base
    jmp @cnt
@nt1:
    sec
    sbc #32
    sta tmpa
    lda #$24
    sta seg_base
    lda #$20
    sta seg2_base
@cnt:
    lda tmpa
    sta seg_col
    lda #32
    sec
    sbc tmpa
    sta seg_cnt
    lda tmpa
    sta seg2_cnt
    rts
.endproc

; A = nametable base high ($20/$24), X = column -> vb_hi / vb_lo
.proc SegAddr
    sta tmpb
    lda nt_slot
    lsr a
    lsr a
    lsr a
    clc
    adc tmpb
    sta vb_hi
    lda nt_slot
    and #7
    asl a
    asl a
    asl a
    asl a
    asl a
    stx tmpb
    ora tmpb
    sta vb_lo
    rts
.endproc

; Write linebuf[0..31] to the row set up by RowSegs.
; Carry clear if the whole row was queued, set if VBUF had no room for part of
; it. A caller that is tracking what the screen shows must not record the row
; as drawn on a set carry -- it has to ask again next frame.
.proc WriteRowSegs
    lda seg_base
    ldx seg_col
    jsr SegAddr
    lda #1
    sta vb_mode
    lda seg_cnt
    sta vb_cnt
    jsr VBufAlloc
    bcs @fail
    ldy #0
@c1:
    lda linebuf,y
    sta (vb_dat),y
    iny
    cpy seg_cnt
    bne @c1
    lda seg2_cnt
    beq @ok
    lda seg2_base
    ldx #0
    jsr SegAddr
    lda #1
    sta vb_mode
    lda seg2_cnt
    sta vb_cnt
    jsr VBufAlloc
    bcs @fail
    ldy #0
    ldx seg_cnt
@c2:
    lda linebuf,x
    sta (vb_dat),y
    inx
    iny
    cpy seg2_cnt
    bne @c2
@ok:
    clc
    rts
@fail:
    sec
    rts
.endproc

; Fill the row set up by RowSegs with the value in A.
.proc FillRowSegs
    sta tmpc
    lda seg_base
    ldx seg_col
    jsr SegAddr
    lda #3
    sta vb_mode
    lda seg_cnt
    sta vb_cnt
    jsr VBufAlloc
    bcs @done
    ldy #0
    lda tmpc
    sta (vb_dat),y
    lda seg2_cnt
    beq @done
    lda seg2_base
    ldx #0
    jsr SegAddr
    lda #3
    sta vb_mode
    lda seg2_cnt
    sta vb_cnt
    jsr VBufAlloc
    bcs @done
    ldy #0
    lda tmpc
    sta (vb_dat),y
@done:
    rts
.endproc

; =============================================================================
; The window job: open and close, spread over frames
; =============================================================================
.proc OpenBox
    lda #0
    sta job_step
    sta box_done
    lda #0
    sta draw_mode
    lda #1
    sta box_open
    rts
.endproc

.proc CloseBox
    lda #0
    sta job_step
    sta box_done
    lda #1
    sta draw_mode
    rts
.endproc

; One step per frame. Sets box_done when the job finishes.
.proc BoxStep
    lda job_step
    cmp #6
    bcc :+
    rts
:   asl a
    tax
    lda step_tab+1,x
    pha
    lda step_tab,x
    pha
    inc job_step
    rts                     ; "return" into the step routine (RTS trick)
.endproc

; step 0/1: blank the window rows to tile $00 (palette-independent)
.proc StepClearA
    lda #BOX_ROW
    ldx #3
    jmp ClearRows
.endproc

.proc StepClearB
    lda #BOX_ROW+3
    ldx #3
    jmp ClearRows
.endproc

; A = first screen row, X = count
.proc ClearRows
    sta box_row_i
    stx box_cnt
@lp:
    lda box_row_i
    jsr RowSegs
    lda #0
    jsr FillRowSegs
    inc box_row_i
    dec box_cnt
    bne @lp
    rts
.endproc

; step 2: attributes. Opening forces the UI palette; closing takes the map's.
.proc StepAttr
    lda cam_ty
    clc
    adc #BOX_ROW
    lsr a
    sta box_row_i           ; first metatile row under the window
    lda #3                  ; the window is exactly 3 metatile rows tall
    sta box_cnt             ; (memory counters: AttrRow* clobbers X and tmpd)
@lp:
    lda draw_mode
    bne @restore
    lda #3
    sta tmp6
    lda box_row_i
    jsr AttrRowForce
    jmp @q
@restore:
    lda box_row_i
    jsr AttrRowShadow
@q:
    jsr QueueAttrRow
    inc box_row_i
    dec box_cnt
    bne @lp
    rts
.endproc

.proc StepDrawA
    lda #BOX_ROW
    ldx #2
    jmp DrawRows
.endproc

.proc StepDrawB
    lda #BOX_ROW+2
    ldx #2
    jmp DrawRows
.endproc

.proc StepDrawC
    lda #BOX_ROW+4
    ldx #2
    jsr DrawRows
    lda #1
    sta box_done
    lda draw_mode
    beq :+
    lda #0
    sta box_open
:   rts
.endproc

; A = first screen row, X = count. Draws the window shell, or restores the map.
.proc DrawRows
    sta box_row_i
    stx box_cnt
@lp:
    lda draw_mode
    bne @map
    lda box_row_i
    jsr ShellRow
    jmp @w
@map:
    lda box_row_i
    jsr MapRow
@w:
    lda box_row_i
    jsr RowSegs
    jsr WriteRowSegs
    inc box_row_i
    dec box_cnt
    bne @lp
    rts
.endproc

; A = screen row -> linebuf holds that row of the window shell.
.proc ShellRow
    sec
    sbc #BOX_ROW
    beq @top
    cmp #BOX_H-1
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
    rts
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
    rts
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
    rts
.endproc

; A = screen row -> linebuf holds the map tiles that belong there.
.proc MapRow
    clc
    adc cam_ty
    jsr BuildRowStrip
    lda cam_tx
    and #63
    tax
    ldy #0
@lp:
    lda stripbuf,x
    sta linebuf,y
    inx
    txa
    and #63
    tax
    iny
    cpy #32
    bne @lp
    rts
.endproc

; =============================================================================
; Messages
; =============================================================================
; A = message id.
.proc SetMessage
    sta tmpa
    lsr a
    lsr a
    lsr a
    lsr a
    lsr a
    lsr a
    clc
    adc #BANK_TEXT_BASE
    sta msg_bank
    jsr SetPrgData
    lda tmpa
    and #63
    asl a
    tay
    lda $8000,y
    sta msg_ptr
    lda $8001,y
    sta msg_ptr+1
    lda #0
    sta cur_line
    rts
.endproc

; Render one line of the current message into linebuf and advance msg_ptr.
; term_action: 0 = line ended normally, 1 = page break, 2 = message end.
.proc RenderLine
    lda msg_bank
    jsr SetPrgData
    lda #F_L
    sta linebuf
    lda #F_R
    sta linebuf+31
    ldx #1
    ldy #0
@lp:
    lda (msg_ptr),y
    cmp #$FD
    bcs @ctrl
    sta linebuf,x
    iny
    inx
    cpx #31
    bcc @lp
    lda #0
    sta term_action
    jmp @adv
@ctrl:
    cmp #$FE
    beq @nl
    cmp #$FD
    beq @pg
    lda #2
    sta term_action
    jmp @eat
@nl:
    lda #0
    sta term_action
    jmp @eat
@pg:
    lda #1
    sta term_action
@eat:
    iny
@adv:
    lda #0
:   cpx #31
    bcs :+
    sta linebuf,x
    inx
    jmp :-
:   tya
    clc
    adc msg_ptr
    sta msg_ptr
    lda msg_ptr+1
    adc #0
    sta msg_ptr+1
    rts
.endproc

; Draw the "more" arrow in the bottom-right of the window.
.proc DrawPrompt
    lda #TILE_ARROW
    sta tmpc
    jmp PutPromptTile
.endproc

.proc ClearPrompt
    lda #0
    sta tmpc
    jmp PutPromptTile
.endproc

.proc PutPromptTile
    lda #TEXT_ROW0+TEXT_LINES-1
    jsr RowSegs
    ; the prompt sits at screen column 29
    lda seg_cnt
    cmp #30
    bcc @second
    lda seg_base
    ldx seg_col
    jsr SegAddr
    lda vb_lo
    clc
    adc #29
    sta vb_lo
    jmp @put
@second:
    lda seg2_base
    ldx #0
    jsr SegAddr
    lda vb_lo
    clc
    adc #29
    sec
    sbc seg_cnt
    sta vb_lo
@put:
    lda #1
    sta vb_mode
    sta vb_cnt
    jsr VBufAlloc
    bcs @done
    ldy #0
    lda tmpc
    sta (vb_dat),y
@done:
    rts
.endproc

; =============================================================================
; Menus — an option list drawn into the window's interior lines
; =============================================================================
; Compose interior line A from a string at ptr, with the cursor if A == the
; highlighted option.
.proc RenderMenuLine
    sta tmpd
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
    lda tmpd
    cmp menu_cursor
    bne :+
    lda #TILE_CURSOR
    sta linebuf+2
:   ldy #0
    ldx #4
@lp:
    lda (ptr),y
    cmp #STR_END
    beq @done
    sta linebuf,x
    iny
    inx
    cpx #31
    bcc @lp
@done:
    lda tmpd
    clc
    adc #TEXT_ROW0
    jsr RowSegs
    jmp WriteRowSegs
.endproc

; Copy the $FF-terminated string at ptr into linebuf starting at X.
.proc PutString
    ldy #0
@lp:
    lda (ptr),y
    cmp #STR_END
    beq @done
    sta linebuf,x
    iny
    inx
    cpx #31
    bcc @lp
@done:
    rts
.endproc

; num_lo/num_hi -> up to 5 decimal digits into linebuf ending at X (right
; aligned); X is left pointing one past the last digit written.
.proc PutNumber
    stx tmpd
    lda #0
    sta loop_j
@div:
    lda num_hi
    sta div_n+1
    lda num_lo
    sta div_n
    lda #10
    sta div_d
    jsr Div16
    lda div_r
    clc
    adc #DIGIT0
    ldx loop_j
    sta digits,x
    inc loop_j
    lda div_q
    sta num_lo
    lda div_q+1
    sta num_hi
    ora num_lo
    bne @div
    ; emit in reverse
    ldx tmpd
    ldy loop_j
@out:
    dey
    lda digits,y
    sta linebuf,x
    inx
    cpy #0
    bne @out
    rts
.endproc

.segment "ENGRO"
; RTS-trick dispatch table for BoxStep (addresses minus one).
step_tab:
    .addr StepClearA-1
    .addr StepClearB-1
    .addr StepAttr-1
    .addr StepDrawA-1
    .addr StepDrawB-1
    .addr StepDrawC-1
