; uikit.inc — the drawing kit behind THRENOS's full-screen menus.
;
; The field menu (bank 26) and the shop / save terminal (bank 29) both live at
; $A000, so they cannot call each other. This file is INCLUDED by each of them:
; every symbol here is module-local, so each bank gets its own private copy.
; Editing this file changes both.
;
; Both screens are their own picture, not a window over the map: they are
; painted with rendering off (ScreenOff / draw 30 rows / ScreenOn) the way
; BattleEnter paints the arena, and the field is repainted by DrawFullMap on
; the way out. The camera is pinned to (0,0) while a menu is up, which is what
; lets RowSegs/WriteRowSegs from text.s address rows as plain $2000 + row*32.
;
; Cursor movement inside a page does NOT repaint: it marks the affected screen
; rows dirty and the pacer flushes at most TWO 32-tile rows per frame, which is
; the vblank budget (see invariant 2 in HANDOFF.md).
;
; The including module must supply:
;   ComposeRow            A = screen row -> linebuf holds that row of the page
;   pg_row0/pg_step/pg_rows/pg_back    page descriptor tables, indexed by page

UI_ROWS   = 30              ; screen rows we own
NOTE_ROW  = 22              ; the one-line notice under every page

; notice ids (0 = no notice)
NT_BATTLE   = 1
NT_NOUSE    = 2
NT_NOEFFECT = 3
NT_NOTP     = 4
NT_NOROOM   = 5
NT_NOCREDIT = 6
NT_SAVED    = 7
NT_NOTHING  = 8
NT_EQUIPPED = 9
NT_BOUGHT   = 10
NT_SOLD     = 11
NT_DONE     = 12

SLASH  = 46                 ; '/' in the font charset (see tools/font.py)

; =============================================================================
; Entering and leaving
; =============================================================================
; Pin the camera to (0,0) and take the party sprite off the screen. The menu
; owns the whole picture until UiExit puts the field back.
.proc UiEnter
    lda #0
    sta cam_x
    sta cam_x+1
    sta cam_y
    sta cam_y+1
    sta cam_tx
    sta cam_ty
    sta scroll_x
    sta scroll_y
    sta ui_note
    sta ui_sp
    sta ui_cur
    sta ui_top
    sta ui_mode
    lda ppu_ctrl
    and #%11111110              ; nametable 0
    sta ppu_ctrl
    ldy #0
    lda #$FF
:   sta OAM_BUF,y
    iny
    bne :-
    jsr DirtyClear
    rts
.endproc

; Back to the field: ReturnToField (bank 30) repaints the map and its music,
; and acts on anything the menu asked for in ui_req.
.proc UiExit
    jmp ReturnToField
.endproc

; =============================================================================
; Putting a composed line on the screen
; =============================================================================
.proc ClearLine
    lda #0
    ldx #33
:   sta linebuf,x
    dex
    bpl :-
    rts
.endproc

; A = screen row: write linebuf straight to VRAM. Rendering must be off.
.proc PutRowDirect
    pha
    lsr a
    lsr a
    lsr a
    clc
    adc #$20
    sta ui_a
    pla
    and #7
    asl a
    asl a
    asl a
    asl a
    asl a
    tax
    lda ui_a
    jsr PpuAddr
    ldy #0
:   lda linebuf,y
    sta PPUDATA
    iny
    cpy #32
    bne :-
    rts
.endproc

; A = screen row: queue linebuf for the next vblank. One 32-tile packet; the
; pacer never queues more than two of these in a frame.
.proc PutRowQueued
    jsr RowSegs
    jmp WriteRowSegs
.endproc

; =============================================================================
; The dirty-row pacer
; =============================================================================
.proc DirtyClear
    lda #0
    sta ui_dirty+0
    sta ui_dirty+1
    sta ui_dirty+2
    sta ui_dirty+3
    rts
.endproc

; A = screen row
.proc DirtyRow
    cmp #UI_ROWS
    bcs @out
    pha
    and #7
    tax
    lda k_bit8,x
    sta ui_a
    pla
    lsr a
    lsr a
    lsr a
    tax
    lda ui_dirty,x
    ora ui_a
    sta ui_dirty,x
@out:
    rts
.endproc

; A = first row, X = count
.proc DirtyRange
    sta ui_row
    stx ui_cnt
@lp:
    lda ui_row
    jsr DirtyRow
    inc ui_row
    dec ui_cnt
    bne @lp
    rts
.endproc

; -> A = the lowest dirty row, cleared from the set. Carry clear if none.
.proc NextDirty
    ldx #0
@lp:
    txa
    and #7
    tay
    lda k_bit8,y
    sta ui_a
    txa
    lsr a
    lsr a
    lsr a
    tay
    lda ui_dirty,y
    and ui_a
    bne @hit
    inx
    cpx #UI_ROWS
    bcc @lp
    clc
    rts
@hit:
    lda ui_a
    eor #$FF
    and ui_dirty,y
    sta ui_dirty,y
    txa
    sec
    rts
.endproc

; Redraw at most two dirty rows. Two 32-tile packets is ~72 bytes of VBUF,
; which is what fits after OAM DMA; a third would be silently truncated.
.proc FlushDirty
    lda #2
    sta ui_cnt
@lp:
    jsr NextDirty
    bcc @done
    sta ui_row
    jsr ComposeRow              ; A = row
    lda ui_row
    jsr PutRowQueued
    dec ui_cnt
    bne @lp
@done:
    rts
.endproc

; =============================================================================
; A whole page, painted with rendering off
; =============================================================================
.proc DrawPage
    jsr ScreenOff
    lda #1
    sta ui_mode
    lda #0
    sta ui_row
@lp:
    lda ui_row
    jsr ComposeRow
    lda ui_row
    jsr PutRowDirect
    inc ui_row
    lda ui_row
    cmp #UI_ROWS
    bcc @lp
    lda #0
    sta ui_mode
    jsr DirtyClear
    jsr UiAttrClear
    jsr UiPalette
    jsr ScreenOn
    rts
.endproc

; Every tile on a menu screen uses BG sub-palette 0.
.proc UiAttrClear
    lda #$23
    ldx #$C0
    jsr PpuAddr
    lda #0
    ldx #64
    jsr PpuFill
    lda #$27
    ldx #$C0
    jsr PpuAddr
    lda #0
    ldx #64
    jmp PpuFill
.endproc

.proc UiPalette
    ldx #0
@lp:
    lda k_pal,x
    sta pal_buf,x
    sta pal_buf+16,x            ; sprite colour 0 must match the backdrop
    inx
    cpx #16
    bne @lp
    lda #<pal_buf
    sta ptr
    lda #>pal_buf
    sta ptr+1
    jmp LoadPalette
.endproc

; =============================================================================
; Numbers
; =============================================================================
; A = an 8-bit value -> ui_n24
.proc Set8
    sta ui_n24
    lda #0
    sta ui_n24+1
    sta ui_n24+2
    rts
.endproc

; A = low, X = high -> ui_n24
.proc Set16
    sta ui_n24
    stx ui_n24+1
    lda #0
    sta ui_n24+2
    rts
.endproc

; ui_n24 /= 10 -> A = the remainder.
.proc Div24By10
    lda #0
    sta ui_rem
    ldx #24
@lp:
    asl ui_n24
    rol ui_n24+1
    rol ui_n24+2
    rol ui_rem
    lda ui_rem
    cmp #10
    bcc @no
    sbc #10
    sta ui_rem
    inc ui_n24
@no:
    dex
    bne @lp
    lda ui_rem
    rts
.endproc

; ui_n24 -> decimal in linebuf, right-aligned with its last digit at column X.
; (text.s's PutNumber is LEFT-aligned from X despite its comment, and is only
; 16-bit; credits and XP are 24-bit.)
.proc PutNumR
    stx ui_col
@lp:
    jsr Div24By10
    clc
    adc #DIGIT0
    ldx ui_col
    sta linebuf,x
    dec ui_col
    lda ui_n24
    ora ui_n24+1
    ora ui_n24+2
    bne @lp
    rts
.endproc

; =============================================================================
; Table lookups (BANK_TABLES is set every time — invariant 6)
; =============================================================================
; A = index -> mul_res = index * NAME_LEN, with BANK_TABLES mapped.
.proc NamePtr
    sta mul_a
    lda #NAME_LEN
    sta mul_b
    jsr Mul8
    lda #BANK_TABLES
    jsr SetPrgData
    rts
.endproc

; A = item id -> ptr = its name
.proc ItemName
    jsr NamePtr
    lda mul_res
    clc
    adc #<item_names
    sta ptr
    lda mul_res+1
    adc #>item_names
    sta ptr+1
    rts
.endproc

; A = class id -> ptr = its name
.proc ClassName
    jsr NamePtr
    lda mul_res
    clc
    adc #<class_names
    sta ptr
    lda mul_res+1
    adc #>class_names
    sta ptr+1
    rts
.endproc

; A = item id -> ui_rec holds its 8-byte record
;   0 kind, 1/2 power, 3/4 price, 5 equip mask, 6 effect, 7 status mask
.proc ItemRec
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
    ldy #0
:   lda (srcp),y
    sta ui_rec,y
    iny
    cpy #ITEM_REC
    bne :-
    rts
.endproc

; A = party slot -> Y = its record offset (slot * 32)
.proc PartyOfs
    asl a
    asl a
    asl a
    asl a
    asl a
    tay
    rts
.endproc

; A = party slot -> A = the bit its class occupies in an item's equip mask
.proc ClassBit
    jsr PartyOfs
    lda party+c_class,y
    and #7
    tax
    lda k_bit8,x
    rts
.endproc

; =============================================================================
; The notice line
; =============================================================================
; A = notice id
.proc SetNote
    sta ui_note
    lda #NOTE_ROW
    jmp DirtyRow
.endproc

.proc ClearNote
    lda ui_note
    beq @none
    lda #0
    sta ui_note
    lda #NOTE_ROW
    jmp DirtyRow
@none:
    rts
.endproc

; Compose the notice row (called by every page's ComposeRow).
.proc NoteLine
    lda ui_note
    beq @none
    sec
    sbc #1
    asl a
    tax
    lda k_notes,x
    sta ptr
    lda k_notes+1,x
    sta ptr+1
    ldx #2
    jmp PutString
@none:
    rts
.endproc

; =============================================================================
; Cursor movement, scrolling and page changes
; =============================================================================
; A = entry index: mark the screen row that shows its cursor dirty.
.proc DirtyEntry
    sec
    sbc ui_top
    bcc @out
    ldx ui_page
    cmp pg_rows,x
    bcs @out
    sta mul_a
    lda pg_step,x
    sta mul_b
    jsr Mul8
    ldx ui_page
    lda mul_res
    clc
    adc pg_row0,x
    jmp DirtyRow
@out:
    rts
.endproc

; Mark every row of the current page's entry list dirty (after a scroll).
.proc DirtyList
    ldx ui_page
    lda pg_rows,x
    sta mul_a
    lda pg_step,x
    sta mul_b
    jsr Mul8
    ldx mul_res
    ldy ui_page
    lda pg_row0,y
    jmp DirtyRange
.endproc

.proc CurUp
    lda ui_max
    beq @none
    lda ui_cur
    jsr DirtyEntry
    dec ui_cur
    lda ui_cur
    bpl @ok
    lda ui_max
    sec
    sbc #1
    sta ui_cur
@ok:
    jmp ScrollFix
@none:
    rts
.endproc

.proc CurDown
    lda ui_max
    beq @none
    lda ui_cur
    jsr DirtyEntry
    inc ui_cur
    lda ui_cur
    cmp ui_max
    bcc @ok
    lda #0
    sta ui_cur
@ok:
    jmp ScrollFix
@none:
    rts
.endproc

; Keep the cursor inside the visible window, scrolling the list if it left it.
.proc ScrollFix
    lda ui_cur
    cmp ui_top
    bcc @above
    sec
    sbc ui_top
    ldx ui_page
    cmp pg_rows,x
    bcs @below
    lda ui_cur                  ; still on screen: two rows change, no more
    jmp DirtyEntry
@above:
    lda ui_cur
    sta ui_top
    jmp DirtyList
@below:
    ldx ui_page
    lda ui_cur
    sec
    sbc pg_rows,x
    clc
    adc #1
    sta ui_top
    jmp DirtyList
.endproc

; A = page: make it current (list rebuilt, cursor home) without drawing.
.proc SetPage
    sta ui_page
    lda #0
    sta ui_cur
    sta ui_top
    jmp PageEnter
.endproc

; A = page: go there and paint it.
.proc GotoPage
    jsr SetPage
    jmp DrawPage
.endproc

; A = page: go there, remembering where we were so B comes back to it.
.proc GotoChild
    pha
    ldx ui_sp
    cpx #6
    bcs :+
    lda ui_cur
    sta ui_stkc,x
    lda ui_top
    sta ui_stkt,x
    inc ui_sp
:   pla
    jmp GotoPage
.endproc

; B: up one page, or out of the menu entirely.
.proc PageBack
    ldx ui_page
    lda pg_back,x
    cmp #$FF
    beq @leave
    jsr SetPage
    ldx ui_sp
    beq @draw
    dex
    stx ui_sp
    lda ui_stkc,x
    sta ui_cur
    lda ui_stkt,x
    sta ui_top
    lda ui_cur                  ; the list may have shrunk under us
    cmp ui_max
    bcc @draw
    lda #0
    sta ui_cur
    sta ui_top
@draw:
    jmp DrawPage
@leave:
    jmp UiExit
.endproc

; Redraw the page we are on without moving anything.
.proc RefreshPage
    lda ui_page
    jsr PageEnter
    lda ui_cur
    cmp ui_max
    bcc :+
    lda #0
    sta ui_cur
    sta ui_top
:   jmp DrawPage
.endproc

; =============================================================================
; Inventory helpers
; =============================================================================
; Build ui_list / ui_lidx from every non-empty inventory slot. -> ui_max
.proc BuildBagList
    ldx #0
    ldy #0
@lp:
    lda inv_id,x
    beq @next
    lda inv_ct,x
    beq @next
    lda inv_id,x
    sta ui_list,y
    txa
    sta ui_lidx,y
    iny
    cpy #32
    bcs @done
@next:
    inx
    cpx #32
    bcc @lp
@done:
    sty ui_max
    rts
.endproc

; X = inventory slot: take one out of the pack.
.proc TakeOne
    dec inv_ct,x
    bne :+
    lda #0
    sta inv_id,x
:   rts
.endproc

; =============================================================================
; Shared read-only data
; =============================================================================
k_bit8: .byte 1, 2, 4, 8, 16, 32, 64, 128

k_pal:
    .byte $0F,$00,$10,$30
    .byte $0F,$00,$10,$30
    .byte $0F,$00,$10,$30
    .byte $0F,$00,$10,$30

k_notes:
    .addr k_n_battle, k_n_nouse, k_n_noeffect, k_n_notp, k_n_noroom
    .addr k_n_nocredit, k_n_saved, k_n_nothing, k_n_equipped
    .addr k_n_bought, k_n_sold, k_n_done

k_n_battle:   .byte "IN BATTLE ONLY", STR_END
k_n_nouse:    .byte "CANNOT USE THAT HERE", STR_END
k_n_noeffect: .byte "NO EFFECT", STR_END
k_n_notp:     .byte "NOT ENOUGH TP", STR_END
k_n_noroom:   .byte "THE PACK IS FULL", STR_END
k_n_nocredit: .byte "NOT ENOUGH CREDITS", STR_END
k_n_saved:    .byte "PROGRESS SAVED", STR_END
k_n_nothing:  .byte "NOTHING TO SHOW", STR_END
k_n_equipped: .byte "EQUIPPED", STR_END
k_n_bought:   .byte "BOUGHT", STR_END
k_n_sold:     .byte "SOLD", STR_END
k_n_done:     .byte "DONE", STR_END
