; shop.s — shops and save terminals. Lives in PRG bank 29 ($A000).
;
; An OB_SHOP object carries a shop id into shop_tab / shop_len; an OB_SAVE
; object stands on every town map and on the first floor of most dungeons.
; Both open a screen of their own, painted with rendering off, exactly like the
; field menu — see src/uikit.inc, which this file includes for the drawing kit.

.include "nes.inc"
.include "zp.inc"
.include "ram.inc"
.include "banks.inc"
.include "gen/charmap.inc"
.include "gen/dataids.inc"

.import SetPrgData, SetPrgCode, PpuAddr, PpuFill, LoadPalette
.import ScreenOff, ScreenOn, Mul8, Div8, Div16
.import PutString, RowSegs, WriteRowSegs
.import ReturnToField, AddItem
.import item_tab, item_names, class_names, shop_tab, shop_len

.ifdef HAVE_SAVEGAME
.import SaveGame                ; src/title.s, landing in parallel
.endif

.export ShopOpen, SaveOpen, ShopTick

; --- pages -------------------------------------------------------------------
S_ROOT  = 0             ; BUY / SELL / LEAVE
S_BUY   = 1
S_SELL  = 2
S_SAVE  = 3             ; the save terminal's yes/no

LIST_ROW = 5            ; row 1 is the heading and row 3 the purse
LIST_N   = 12
OPT_ROW  = 6

; BUG (data, not code): tools/areas.py places TWELVE OB_SHOP objects — two in
; each of the six towns — but gamedata.SHOPS defines only EIGHT stock tables,
; so shop ids 8..11 (both shops in Dustgate and both in Lastport) index past
; shop_len straight into inn_tab and would stock garbage. tools/gamedata.py is
; owned elsewhere in this branch, so the id is clamped here instead: those four
; shops sell the last table's stock rather than nonsense. Delete the clamp once
; SHOPS has one entry per shop object.
N_SHOPS = 8

.segment "BANK29"

.include "uikit.inc"

; =============================================================================
; Opening
; =============================================================================
; A = shop id.
.proc ShopOpen
    cmp #N_SHOPS                ; see the note by N_SHOPS
    bcc :+
    lda #N_SHOPS-1
:   sta ui_shop
    jsr UiEnter
    lda #0
    sta ui_req
    lda #S_ROOT
    jmp GotoPage
.endproc

.proc SaveOpen
    jsr UiEnter
    lda #0
    sta ui_req
    lda #S_SAVE
    jmp GotoPage
.endproc

.proc ShopTick
    jsr FlushDirty
    lda pad1_new
    beq @done
    jsr ClearNote
    lda pad1_new
    and #BTN_UP
    beq @nu
    jmp CurUp
@nu:
    lda pad1_new
    and #BTN_DOWN
    beq @nd
    jmp CurDown
@nd:
    lda pad1_new
    and #BTN_B
    beq @nb
    jmp PageBack
@nb:
    lda pad1_new
    and #BTN_A
    beq @done
    jmp PageAct
@done:
    rts
.endproc

; =============================================================================
; Dispatch
; =============================================================================
.proc ComposeRow
    pha
    jsr ClearLine
    ldx ui_page
    lda comp_l,x
    sta ui_ptr
    lda comp_h,x
    sta ui_ptr+1
    pla
    cmp #NOTE_ROW
    bne @page
    jmp NoteLine
@page:
    jmp (ui_ptr)
.endproc

.proc PageEnter
    ldx ui_page
    lda ente_l,x
    sta ui_ptr
    lda ente_h,x
    sta ui_ptr+1
    jmp (ui_ptr)
.endproc

.proc PageAct
    ldx ui_page
    lda acti_l,x
    sta ui_ptr
    lda acti_h,x
    sta ui_ptr+1
    jmp (ui_ptr)
.endproc

.proc TitleLine
    lda ui_page
    asl a
    tax
    lda pg_title,x
    sta ptr
    lda pg_title+1,x
    sta ptr+1
    ldx #2
    jmp PutString
.endproc

; The purse, on row 3 of every shop page.
.proc CreditLine
    lda #<s_credits
    sta ptr
    lda #>s_credits
    sta ptr+1
    ldx #2
    jsr PutString
    lda credits
    sta ui_n24
    lda credits+1
    sta ui_n24+1
    lda credits+2
    sta ui_n24+2
    ldx #20
    jmp PutNumR
.endproc

; =============================================================================
; S_ROOT
; =============================================================================
.proc EnterRoot
    lda #3
    sta ui_max
    rts
.endproc

.proc RowRoot
    cmp #1
    beq @title
    cmp #3
    beq @cred
    sec
    sbc #OPT_ROW
    bcc @out
    cmp #3
    bcs @out
    sta ui_a
    cmp ui_cur
    bne @nocur
    lda #TILE_CURSOR
    sta linebuf+1
@nocur:
    lda ui_a
    asl a
    tax
    lda s_rootopt,x
    sta ptr
    lda s_rootopt+1,x
    sta ptr+1
    ldx #3
    jmp PutString
@title:
    jmp TitleLine
@cred:
    jmp CreditLine
@out:
    rts
.endproc

.proc ActRoot
    lda ui_cur
    beq @buy
    cmp #1
    beq @sell
    jmp UiExit
@buy:
    lda #S_BUY
    jmp GotoChild
@sell:
    lda #S_SELL
    jmp GotoChild
.endproc

; =============================================================================
; S_BUY — this shop's stock
; =============================================================================
.proc EnterBuy
    lda #BANK_TABLES
    jsr SetPrgData
    ldx ui_shop
    lda shop_len,x
    sta ui_max
    lda ui_shop                 ; eight item ids per shop
    asl a
    asl a
    asl a
    tay
    ldx #0
@lp:
    cpx ui_max
    bcs @done
    lda shop_tab,y
    sta ui_list,x
    iny
    inx
    bne @lp
@done:
    rts
.endproc

.proc RowBuy
    cmp #1
    beq @title
    cmp #3
    beq @cred
    sec
    sbc #LIST_ROW
    bcc @out
    cmp #LIST_N
    bcs @out
    clc
    adc ui_top
    cmp ui_max
    bcs @out
    sta ui_a
    cmp ui_cur
    bne @nocur
    lda #TILE_CURSOR
    sta linebuf+1
@nocur:
    ldx ui_a
    lda ui_list,x
    jsr ItemName
    ldx #3
    jsr PutString
    ldx ui_a
    lda ui_list,x
    jsr ItemRec
    lda ui_rec+3
    ldx ui_rec+4
    jsr Set16
    ldx #21
    jsr PutNumR
    jmp WhoCanUse
@title:
    jmp TitleLine
@cred:
    jmp CreditLine
@out:
    rts
.endproc

; The four digits at the right of a stock line: which party members may carry
; the piece of gear on this row. Consumables show nothing.
.proc WhoCanUse
    lda ui_rec+0
    beq @out                    ; kind 0: not gear
    cmp #5
    bcs @out                    ; consumables and key items
    lda #0
    sta ui_b
@lp:
    lda ui_b
    cmp party_n
    bcs @out
    lda ui_b
    jsr ClassBit
    and ui_rec+5
    beq @next
    lda ui_b
    clc
    adc #DIGIT0+1
    ldx ui_b
    sta linebuf+24,x
@next:
    inc ui_b
    lda ui_b
    cmp #4
    bcc @lp
@out:
    rts
.endproc

.proc ActBuy
    lda ui_max
    bne @go
    rts
@go:
    ldx ui_cur
    lda ui_list,x
    sta ui_item
    jsr ItemRec
    ; can we afford it? (24-bit purse against a 16-bit price)
    lda credits+2
    bne @afford
    lda credits+1
    cmp ui_rec+4
    bcc @poor
    bne @afford
    lda credits
    cmp ui_rec+3
    bcc @poor
@afford:
    lda ui_item
    ldy #1
    jsr AddItem
    bcc @paid
    lda #NT_NOROOM
    jmp SetNote
@paid:
    lda credits
    sec
    sbc ui_rec+3
    sta credits
    lda credits+1
    sbc ui_rec+4
    sta credits+1
    lda credits+2
    sbc #0
    sta credits+2
    lda #3                      ; the purse changed
    jsr DirtyRow
    lda #NT_BOUGHT
    jmp SetNote
@poor:
    lda #NT_NOCREDIT
    jmp SetNote
.endproc

; =============================================================================
; S_SELL — the pack, at half price
; =============================================================================
; Anything with no price (key items and the story gear) cannot be sold.
.proc EnterSell
    lda #0
    sta ui_a                    ; inventory slot
    sta ui_b                    ; entries found
@lp:
    ldx ui_a
    lda inv_id,x
    beq @next
    lda inv_ct,x
    beq @next
    ldx ui_a
    lda inv_id,x
    jsr ItemRec
    lda ui_rec+3
    ora ui_rec+4
    beq @next
    ldx ui_a
    ldy ui_b
    lda inv_id,x
    sta ui_list,y
    lda ui_a
    sta ui_lidx,y
    inc ui_b
@next:
    inc ui_a
    lda ui_a
    cmp #32
    bcc @lp
    lda ui_b
    sta ui_max
    rts
.endproc

.proc RowSell
    cmp #1
    beq @title
    cmp #3
    beq @cred
    sec
    sbc #LIST_ROW
    bcc @out
    cmp #LIST_N
    bcs @out
    clc
    adc ui_top
    cmp ui_max
    bcs @out
    sta ui_a
    cmp ui_cur
    bne @nocur
    lda #TILE_CURSOR
    sta linebuf+1
@nocur:
    ldx ui_a
    lda ui_list,x
    jsr ItemName
    ldx #3
    jsr PutString
    ldx ui_a
    ldy ui_lidx,x
    lda inv_ct,y
    jsr Set8
    ldx #17
    jsr PutNumR
    ldx ui_a
    lda ui_list,x
    jsr HalfPrice
    ldx #26
    jmp PutNumR
@title:
    jmp TitleLine
@cred:
    jmp CreditLine
@out:
    rts
.endproc

; A = item id -> ui_n24 = half its price, and ui_rec holds its record.
.proc HalfPrice
    jsr ItemRec
    lda ui_rec+4
    lsr a
    sta ui_n24+1
    lda ui_rec+3
    ror a
    sta ui_n24
    lda #0
    sta ui_n24+2
    rts
.endproc

.proc ActSell
    lda ui_max
    bne @go
    rts
@go:
    ldx ui_cur
    lda ui_list,x
    sta ui_item
    lda ui_lidx,x
    sta ui_islot
    lda ui_item
    jsr HalfPrice
    lda credits
    clc
    adc ui_n24
    sta credits
    lda credits+1
    adc ui_n24+1
    sta credits+1
    lda credits+2
    adc #0
    sta credits+2
    bcc @ok
    lda #$FF                    ; saturate rather than wrap
    sta credits
    sta credits+1
    sta credits+2
@ok:
    ldx ui_islot
    jsr TakeOne
    jsr RefreshPage
    lda #NT_SOLD
    jmp SetNote
.endproc

; =============================================================================
; S_SAVE — the save terminal
; =============================================================================
.proc EnterSave
    lda #2
    sta ui_max
    rts
.endproc

.proc RowSave
    cmp #1
    beq @title
    cmp #3
    beq @ask
    sec
    sbc #OPT_ROW
    bcc @out
    cmp #2
    bcs @out
    sta ui_a
    cmp ui_cur
    bne @nocur
    lda #TILE_CURSOR
    sta linebuf+1
@nocur:
    lda ui_a
    asl a
    tax
    lda s_yesno,x
    sta ptr
    lda s_yesno+1,x
    sta ptr+1
    ldx #3
    jmp PutString
@title:
    jmp TitleLine
@ask:
    lda #<s_ask
    sta ptr
    lda #>s_ask
    sta ptr+1
    ldx #2
    jmp PutString
@out:
    rts
.endproc

.proc ActSave
    lda ui_cur
    beq @yes
    jmp UiExit                  ; NO
@yes:
.ifdef HAVE_SAVEGAME
    jsr SaveGame
.else
    jsr SaveStub
.endif
    lda #NT_SAVED
    jmp SetNote
.endproc

.ifndef HAVE_SAVEGAME
; ---------------------------------------------------------------------------
; STUB. The real SaveGame lives in src/title.s, which is landing on the main
; branch in parallel with this file and is not in this worktree. Build with
; -D HAVE_SAVEGAME (and drop this proc) once it is there; the call site above
; is already written.
; ---------------------------------------------------------------------------
.proc SaveStub
    rts
.endproc
.endif

; =============================================================================
; Tables
; =============================================================================
comp_l: .byte <RowRoot, <RowBuy, <RowSell, <RowSave
comp_h: .byte >RowRoot, >RowBuy, >RowSell, >RowSave
ente_l: .byte <EnterRoot, <EnterBuy, <EnterSell, <EnterSave
ente_h: .byte >EnterRoot, >EnterBuy, >EnterSell, >EnterSave
acti_l: .byte <ActRoot, <ActBuy, <ActSell, <ActSave
acti_h: .byte >ActRoot, >ActBuy, >ActSell, >ActSave

;        ROOT BUY SELL SAVE
pg_row0: .byte  6,  5,  5,  6
pg_step: .byte  1,  1,  1,  1
pg_rows: .byte  3, 12, 12,  2
pg_back: .byte $FF,  0,  0, $FF

pg_title: .addr s_t_shop, s_t_buy, s_t_sell, s_t_save

s_credits: .byte "CREDITS", STR_END
s_ask:     .byte "RECORD YOUR PROGRESS?", STR_END

s_rootopt: .addr s_r_buy, s_r_sell, s_r_leave
s_r_buy:   .byte "BUY", STR_END
s_r_sell:  .byte "SELL", STR_END
s_r_leave: .byte "LEAVE", STR_END

s_yesno:   .addr s_yes, s_no
s_yes:     .byte "YES", STR_END
s_no:      .byte "NO", STR_END

s_t_shop:  .byte "SHOP", STR_END
s_t_buy:   .byte "BUY", STR_END
s_t_sell:  .byte "SELL", STR_END
s_t_save:  .byte "SAVE TERMINAL", STR_END
