; title.s — the title screen, squad muster, and the battery save file.
; Lives in PRG bank 27 (TITLE_BANK), mapped at $A000 while it runs.
;
; Two full screens, each painted with rendering off. The in-place rule that
; governs field windows does not apply here: there is no map underneath to
; preserve, and a repaint that takes several frames would be visible as a tear.
;
;   the title    the painted logo screen from tools/title_art.py, with
;                NEW GAME / CONTINUE under it. CONTINUE is only offered when
;                the battery holds a file that checksums.
;   the muster   a plain framed screen where the four party slots are filled by
;                picking a class each, with that class's opening stats.
;
; Everything drawn after the repaint goes through the row queue: one screen row
; is a 36-byte VBUF packet and the vblank budget is about 100 bytes, so at most
; two rows are pushed per frame. Painting six list rows in one frame silently
; truncated the queue -- the same failure the battle menus hit.
;
; The save file lives here because the title is its only other reader. The live
; game state IS $6006-$61FF, so SaveGame copies that block into the slot at
; $6200 behind a magic word and a checksum, and LoadGame copies it back. Without
; the copy every step the party took would already be permanent.

.include "nes.inc"
.include "zp.inc"
.include "ram.inc"
.include "banks.inc"
.include "gen/charmap.inc"
.include "gen/dataids.inc"
.include "gen/songids.inc"
.include "gen/titleids.inc"

.import SetPrgData, SetPrgCode, SetChrBank, PpuAddr, PpuFill, LoadPalette
.import ScreenOff, ScreenOn, VBufAlloc, Mul8, PutNumber, PutString
.import title_nt, title_attr, title_pal
.import class_tab, class_names, class_vets
.import StartNewGame, StartLoadedGame

.export TitleEnter, TitleTick, SaveGame, LoadGame, SaveValid

TI_MENU   = 0
TI_MUSTER = 1
TI_READY  = 2

N_SLOTS   = 4

; muster-screen rows
ROW_BANNER = 2
ROW_SLOT0  = 4
ROW_PROMPT = 7
ROW_LIST   = 9
ROW_STATS  = 16
ROW_HELP   = 20

; title-screen rows
ROW_NEW    = 22
ROW_CONT   = 24

Q_BASE     = 2          ; ti_rowq[0] is screen row 2
Q_LEN      = 24

; the muster's window frame
FRAME_TOP  = 1
FRAME_BOT  = 22
FRAME_W    = 30         ; columns 1..30

F_TL = TILE_FRAME + 0
F_T  = TILE_FRAME + 1
F_TR = TILE_FRAME + 2
F_L  = TILE_FRAME + 3
F_R  = TILE_FRAME + 5
F_BL = TILE_FRAME + 6
F_B  = TILE_FRAME + 7
F_BR = TILE_FRAME + 8

.segment "BANK27"

; =============================================================================
; Entry
; =============================================================================
.proc TitleEnter
    jsr SaveValid
    lda #0
    rol a                       ; carry -> 1 when a file is there
    sta ti_has_save
    lda #TI_MENU
    sta ti_state
    lda #0
    sta ti_cursor
    sta ti_slot
    jsr PaintTitle
    lda #SONG_TITLE
    sta music_req
    rts
.endproc

; =============================================================================
; Per-frame
; =============================================================================
.proc TitleTick
    jsr FlushQueue
    lda ti_state
    cmp #TI_MENU
    bne :+
    jmp TickMenu
:   cmp #TI_MUSTER
    bne :+
    jmp TickMuster
:   jmp TickReady
.endproc

; --- NEW GAME / CONTINUE -----------------------------------------------------
.proc TickMenu
    lda ti_has_save
    beq @nomove                 ; one option only: nothing to move between
    lda pad1_new
    and #(BTN_UP | BTN_DOWN)
    beq @nomove
    lda ti_cursor
    eor #1
    sta ti_cursor
    lda #SFX_CURSOR
    sta sfx_req
    lda #ROW_NEW
    jsr MarkRow
    lda #ROW_CONT
    jsr MarkRow
@nomove:
    lda pad1_new
    and #(BTN_A | BTN_START)
    beq @done
    lda #SFX_CONFIRM
    sta sfx_req
    lda ti_cursor
    beq @new
    jsr LoadGame
    bcc @new                    ; a file that stopped checksumming: start over
    jmp StartLoadedGame
@new:
    jsr ClearPicks
    lda #TI_MUSTER
    sta ti_state
    jmp PaintMuster
@done:
    rts
.endproc

.proc ClearPicks
    lda #$FF
    ldx #0
:   sta party_class,x
    inx
    cpx #N_SLOTS
    bne :-
    lda #0
    sta ti_slot
    sta ti_cursor
    rts
.endproc

; --- picking a class per slot ------------------------------------------------
.proc TickMuster
    lda pad1_new
    and #BTN_UP
    beq :+
    lda ti_cursor
    bne @up
    lda #N_CLASSES
@up:
    sec
    sbc #1
    jmp @moved
:   lda pad1_new
    and #BTN_DOWN
    beq @nomove
    lda ti_cursor
    clc
    adc #1
    cmp #N_CLASSES
    bcc @moved
    lda #0
@moved:
    sta ti_cursor
    lda #SFX_CURSOR
    sta sfx_req
    jsr MarkList
    jsr MarkStats
@nomove:
    lda pad1_new
    and #BTN_B
    beq @nob
    lda ti_slot                 ; step back a slot and re-pick it
    beq @nob
    sec
    sbc #1
    sta ti_slot
    tax
    lda #$FF
    sta party_class,x
    lda #SFX_CANCEL
    sta sfx_req
    jsr MarkSlots
    lda #ROW_PROMPT
    jmp MarkRow
@nob:
    lda pad1_new
    and #(BTN_A | BTN_START)
    beq @done
    ldx ti_slot
    lda ti_cursor
    sta party_class,x
    lda #SFX_CONFIRM
    sta sfx_req
    inc ti_slot
    jsr MarkSlots
    lda ti_slot
    cmp #N_SLOTS
    bcc @more
    lda #TI_READY
    sta ti_state
    lda #0
    sta ti_cursor
    jsr MarkReady
    rts
@more:
    lda #ROW_PROMPT
    jmp MarkRow
@done:
    rts
.endproc

; --- MAKE PLANETFALL / START OVER -------------------------------------------
.proc TickReady
    lda pad1_new
    and #(BTN_UP | BTN_DOWN)
    beq @nomove
    lda ti_cursor
    eor #1
    sta ti_cursor
    lda #SFX_CURSOR
    sta sfx_req
    jsr MarkReady
@nomove:
    lda pad1_new
    and #BTN_B
    bne @back
    lda pad1_new
    and #(BTN_A | BTN_START)
    beq @done
    lda ti_cursor
    bne @back
    lda #SFX_CONFIRM
    sta sfx_req
    jmp StartNewGame            ; never comes back
@back:
    lda #SFX_CANCEL
    sta sfx_req
    jsr ClearPicks
    lda #TI_MUSTER
    sta ti_state
    jmp PaintMuster
@done:
    rts
.endproc

; =============================================================================
; Whole-screen repaints (rendering off)
; =============================================================================
.proc PaintTitle
    jsr ScreenOff
    lda #CHR_TITLE              ; the logo art takes over BG $80-$FF
    ldx #SEL_CHR4
    jsr SetChrBank
    lda #CHR_TITLE+1
    ldx #SEL_CHR5
    jsr SetChrBank

    lda #BANK_TITLE_DATA
    jsr SetPrgData
    lda #$20
    ldx #$00
    jsr PpuAddr
    lda #<title_nt
    sta srcp
    lda #>title_nt
    sta srcp+1
    ldx #0
@page:                          ; 960 bytes = three full pages plus 192
    ldy #0
:   lda (srcp),y
    sta PPUDATA
    iny
    bne :-
    inc srcp+1
    inx
    cpx #3
    bne @page
    ldy #0
:   lda (srcp),y
    sta PPUDATA
    iny
    cpy #192
    bne :-
    ldy #0                      ; attributes follow contiguously at $23C0
:   lda title_attr,y
    sta PPUDATA
    iny
    cpy #64
    bne :-

    jsr BlankNt1
    lda #<title_pal
    sta ptr
    lda #>title_pal
    sta ptr+1
    jsr LoadPalette
    jsr FinishPaint
    lda #ROW_NEW
    jsr MarkRow
    lda #ROW_CONT
    jmp MarkRow
.endproc

.proc PaintMuster
    jsr ScreenOff
    lda #$20
    ldx #$00
    jsr PpuAddr
    lda #0
    ldy #4                      ; nametable 0 and its attribute table
:   ldx #0
    jsr PpuFill
    dey
    bne :-
    lda #$23                    ; every quadrant on the UI sub-palette
    ldx #$C0
    jsr PpuAddr
    lda #%11111111
    ldx #64
    jsr PpuFill
    jsr DrawFrame
    jsr BlankNt1
    jsr FinishPaint

    lda #ROW_BANNER
    jsr MarkRow
    jsr MarkSlots
    lda #ROW_PROMPT
    jsr MarkRow
    jsr MarkList
    jsr MarkStats
    lda #ROW_HELP
    jmp MarkRow
.endproc

; A window frame around the muster, drawn once with rendering off. The row
; queue keeps the two vertical edges alive: PushRow writes all 32 columns, so
; ComposeRow puts F_L and F_R back into every line it composes.
.proc DrawFrame
    lda #$20                    ; top border: row FRAME_TOP
    ldx #(FRAME_TOP*32)+1
    jsr PpuAddr
    lda #F_TL
    sta PPUDATA
    lda #F_T
    ldx #FRAME_W-2
    jsr PpuFill
    lda #F_TR
    sta PPUDATA

    lda #FRAME_TOP+1
    sta ti_row
@side:
    lda ti_row
    jsr FrameRowAddr
    lda #F_L
    sta PPUDATA
    lda ti_row                  ; the right edge needs its own address
    jsr FrameRowAddr
    lda vb_lo
    clc
    adc #FRAME_W-1
    tax
    lda vb_hi
    jsr PpuAddr
    lda #F_R
    sta PPUDATA
    inc ti_row
    lda ti_row
    cmp #FRAME_BOT
    bcc @side

    lda ti_row
    jsr FrameRowAddr
    lda #F_BL
    sta PPUDATA
    lda #F_B
    ldx #FRAME_W-2
    jsr PpuFill
    lda #F_BR
    sta PPUDATA
    rts
.endproc

; A = screen row -> the PPU address of column 1 on it, in vb_hi/vb_lo, with
; PPUADDR already pointed there.
.proc FrameRowAddr
    pha
    lsr a
    lsr a
    lsr a
    clc
    adc #$20
    sta vb_hi
    pla
    and #7
    asl a
    asl a
    asl a
    asl a
    asl a
    clc
    adc #1
    sta vb_lo
    lda vb_hi
    ldx vb_lo
    jmp PpuAddr
.endproc

; The second nametable is never scrolled to, but whatever the field left in it
; shows through the overscan seam.
.proc BlankNt1
    lda #$24
    ldx #$00
    jsr PpuAddr
    lda #0
    ldy #4
:   ldx #0
    jsr PpuFill
    dey
    bne :-
    rts
.endproc

.proc FinishPaint
    lda #$FF                    ; park every sprite off-screen
    ldx #0
:   sta OAM_BUF,x
    inx
    bne :-
    lda #0
    sta scroll_x
    sta scroll_y
    jsr ClearQueue
    jmp ScreenOn
.endproc

; =============================================================================
; The row queue
; =============================================================================
.proc ClearQueue
    lda #0
    ldx #0
:   sta ti_rowq,x
    inx
    cpx #Q_LEN
    bne :-
    rts
.endproc

; A = screen row.
.proc MarkRow
    sec
    sbc #Q_BASE
    cmp #Q_LEN
    bcs @done
    tax
    lda #1
    sta ti_rowq,x
@done:
    rts
.endproc

.proc MarkSlots
    lda #ROW_SLOT0
    jsr MarkRow
    lda #ROW_SLOT0+1
    jmp MarkRow
.endproc

.proc MarkList
    lda #N_CLASSES
    sta ti_cnt
    lda #ROW_LIST
    sta ti_tmp2
:   lda ti_tmp2
    jsr MarkRow
    inc ti_tmp2
    dec ti_cnt
    bne :-
    rts
.endproc

.proc MarkStats
    lda #ROW_STATS
    jsr MarkRow
    lda #ROW_STATS+1
    jsr MarkRow
    lda #ROW_STATS+2
    jmp MarkRow
.endproc

; The ready panel replaces the class list, so every list row is redrawn -- and
; the stat rows too, or they keep previewing whatever the cursor last sat on.
.proc MarkReady
    lda #ROW_PROMPT
    jsr MarkRow
    jsr MarkStats
    jmp MarkList
.endproc

; Redraw at most two marked rows. The counter lives in ti_flush, not ti_cnt:
; RowSlot and StatField both use ti_cnt, and they run underneath this loop.
.proc FlushQueue
    lda #2
    sta ti_flush
@lp:
    ldx #0
@scan:
    lda ti_rowq,x
    bne @hit
    inx
    cpx #Q_LEN
    bcc @scan
    rts
@hit:
    lda #0
    sta ti_rowq,x
    txa
    clc
    adc #Q_BASE
    sta ti_row
    jsr ComposeRow
    lda ti_row
    jsr PushRow
    dec ti_flush
    bne @lp
    rts
.endproc

; A = screen row. Pushes linebuf[0..31] to nametable 0 through VBUF.
.proc PushRow
    pha
    lsr a
    lsr a
    lsr a
    clc
    adc #$20
    sta vb_hi
    pla
    and #7
    asl a
    asl a
    asl a
    asl a
    asl a
    sta vb_lo
    lda #1
    sta vb_mode
    lda #32
    sta vb_cnt
    jsr VBufAlloc
    bcs @done
    ldy #0
:   lda linebuf,y
    sta (vb_dat),y
    iny
    cpy #32
    bne :-
@done:
    rts
.endproc

.proc ClearLine
    lda #0
    ldx #0
:   sta linebuf,x
    inx
    cpx #32
    bne :-
    rts
.endproc

; =============================================================================
; Row composition: ti_row says which row, the state says what belongs on it
; =============================================================================
.proc ComposeRow
    jsr ClearLine
    lda ti_state
    bne @framed
    jmp @menu
@framed:
    lda #F_L                    ; keep the muster's frame edges alive
    sta linebuf+1
    lda #F_R
    sta linebuf+30
    jmp @game
@menu:
    ; --- the title menu ---
    lda ti_row
    cmp #ROW_NEW
    bne @cont
    lda #0
    jsr Cursor8
    lda #<s_new
    ldx #>s_new
    jmp PutAt10
@cont:
    lda ti_has_save
    beq @out                    ; no file: the CONTINUE line stays blank
    lda #1
    jsr Cursor8
    lda #<s_cont
    ldx #>s_cont
    jmp PutAt10
@game:
    lda ti_row
    cmp #ROW_BANNER
    bne :+
    lda #<s_muster
    ldx #>s_muster
    jmp PutAt4
:   cmp #ROW_SLOT0
    bcc @out
    cmp #ROW_SLOT0+2
    bcs :+
    jmp RowSlot
:   cmp #ROW_PROMPT
    bne :+
    jmp RowPrompt
:   cmp #ROW_LIST
    bcc @out
    cmp #ROW_LIST+N_CLASSES
    bcs :+
    jmp RowList
:   cmp #ROW_STATS
    bcc @out
    cmp #ROW_STATS+3
    bcs :+
    jmp RowStats
:   cmp #ROW_HELP
    bne @out
    lda #<s_help
    ldx #>s_help
    jmp PutAt4
@out:
    rts
.endproc

; A = the option this row stands for: draw the cursor if it is selected.
.proc Cursor8
    cmp ti_cursor
    bne @no
    lda #TILE_CURSOR
    sta linebuf+8
@no:
    rts
.endproc

.proc PutAt10
    sta ptr
    stx ptr+1
    ldx #10
    jmp PutString
.endproc

.proc PutAt4
    sta ptr
    stx ptr+1
    ldx #4
    jmp PutString
.endproc

; --- "1 SOLDIER        3 -" --------------------------------------------------
.proc RowSlot
    lda ti_row
    sec
    sbc #ROW_SLOT0
    sta ti_tmp                  ; 0 or 1
    sta ti_cnt                  ; left slot = the row number
    ldx #4
    jsr SlotField
    lda ti_tmp
    clc
    adc #2
    sta ti_cnt                  ; right slot
    ldx #18
    jmp SlotField
.endproc

; ti_cnt = slot number, X = the column its label starts at.
.proc SlotField
    stx ti_tmp2
    lda ti_cnt
    clc
    adc #DIGIT0+1               ; slots are numbered 1..4 on screen
    ldx ti_tmp2
    sta linebuf,x
    ldx ti_cnt
    lda party_class,x
    cmp #$FF
    bne @named
    lda #<s_empty
    ldx #>s_empty
    jmp @put
@named:
    jsr ClassNamePtr
    lda ptr
    ldx ptr+1
@put:
    sta ptr
    stx ptr+1
    lda ti_tmp2
    clc
    adc #2
    tax
    jmp PutString
.endproc

.proc RowPrompt
    lda ti_state
    cmp #TI_READY
    bne @pick
    lda #<s_ready
    ldx #>s_ready
    jmp PutAt4
@pick:
    lda #<s_pick
    ldx #>s_pick
    jsr PutAt4
    lda ti_slot
    clc
    adc #DIGIT0+1
    sta linebuf+16
    rts
.endproc

; The list rows carry the class list while mustering and the two confirm
; options once the squad is full.
.proc RowList
    lda ti_state
    cmp #TI_READY
    beq @ready
    lda ti_row
    sec
    sbc #ROW_LIST
    sta ti_tmp
    cmp ti_cursor
    bne :+
    lda #TILE_CURSOR
    sta linebuf+3
:   lda ti_tmp
    jsr ClassNamePtr
    ldx #5
    jsr PutString
    lda ti_tmp
    jsr ClassVetPtr
    ldx #18
    jmp PutString
@ready:
    lda ti_row
    sec
    sbc #ROW_LIST
    cmp #2
    bcs @blank                  ; the rest of the old list is cleared
    sta ti_tmp
    cmp ti_cursor
    bne :+
    lda #TILE_CURSOR
    sta linebuf+3
:   lda ti_tmp
    bne :+
    lda #<s_begin
    ldx #>s_begin
    jmp PutAt5
:   lda #<s_over
    ldx #>s_over
    jmp PutAt5
@blank:
    rts
.endproc

.proc PutAt5
    sta ptr
    stx ptr+1
    ldx #5
    jmp PutString
.endproc

; --- the stat panel for the class under the cursor ---------------------------
.proc RowStats
    lda ti_state
    cmp #TI_READY
    beq @out                    ; the squad is chosen; nothing to preview
    lda ti_row
    sec
    sbc #ROW_STATS
    sta ti_tmp2                 ; 0 = HP/TP, 1 = STR/AGI, 2 = VIT/SPI
    ldx #4
    ldy #0
    jsr StatField
    ldx #16
    ldy #1
    jmp StatField
@out:
    rts
.endproc

; X = column, Y = 0 for the left stat of the pair, 1 for the right.
.proc StatField
    stx ti_tmp
    sty ti_cnt
    lda ti_cursor
    jsr ClassRecPtr             ; srcp -> the class record, BANK_TABLES mapped
    lda ti_tmp2
    asl a
    clc
    adc ti_cnt                  ; label index = pair*2 + side
    asl a
    tax
    lda stat_lbl,x
    sta ptr
    lda stat_lbl+1,x
    sta ptr+1
    ldx ti_tmp
    jsr PutString
    lda ti_tmp2                 ; the record's stats are in the same order
    asl a
    clc
    adc ti_cnt
    tay
    lda (srcp),y
    sta num_lo
    lda #0
    sta num_hi
    lda ti_tmp
    clc
    adc #5
    tax
    jmp PutNumber
.endproc

; A = class -> ptr = its name, with BANK_TABLES mapped.
.proc ClassNamePtr
    jsr ClassOffset
    lda mul_res
    clc
    adc #<class_names
    sta ptr
    lda mul_res+1
    adc #>class_names
    sta ptr+1
    rts
.endproc

.proc ClassVetPtr
    jsr ClassOffset
    lda mul_res
    clc
    adc #<class_vets
    sta ptr
    lda mul_res+1
    adc #>class_vets
    sta ptr+1
    rts
.endproc

.proc ClassOffset
    sta mul_a
    lda #NAME_LEN
    sta mul_b
    jsr Mul8
    lda #BANK_TABLES
    jmp SetPrgData
.endproc

; A = class -> srcp = its 16-byte record, with BANK_TABLES mapped.
.proc ClassRecPtr
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
    rts
.endproc

; =============================================================================
; The save file
; =============================================================================
; Copy SLOT_LEN bytes srcp -> dstp. Both pointers are consumed.
.proc CopyBlock
    lda #0
    sta ti_cnt
    sta ti_tmp
    ldy #0
@lp:
    lda (srcp),y
    sta (dstp),y
    iny
    bne :+
    inc srcp+1
    inc dstp+1
:   inc ti_cnt
    bne :+
    inc ti_tmp
:   lda ti_tmp
    cmp #>SLOT_LEN
    bne @lp
    lda ti_cnt
    cmp #<SLOT_LEN
    bne @lp
    rts
.endproc

; Sum SLOT_LEN bytes at srcp into ti_sum. srcp is consumed.
.proc SumBlock
    lda #0
    sta ti_sum
    sta ti_sum+1
    sta ti_cnt
    sta ti_tmp
    ldy #0
@lp:
    lda (srcp),y
    clc
    adc ti_sum
    sta ti_sum
    lda ti_sum+1
    adc #0
    sta ti_sum+1
    iny
    bne :+
    inc srcp+1
:   inc ti_cnt
    bne :+
    inc ti_tmp
:   lda ti_tmp
    cmp #>SLOT_LEN
    bne @lp
    lda ti_cnt
    cmp #<SLOT_LEN
    bne @lp
    rts
.endproc

.proc SaveGame
    lda #<sav_version
    sta srcp
    lda #>sav_version
    sta srcp+1
    lda #<slot_data
    sta dstp
    lda #>slot_data
    sta dstp+1
    jsr CopyBlock
    lda #<slot_data
    sta srcp
    lda #>slot_data
    sta srcp+1
    jsr SumBlock
    lda ti_sum
    sta slot_sum
    lda ti_sum+1
    sta slot_sum+1
    ldx #3
:   lda magic,x
    sta slot_magic,x
    dex
    bpl :-
    rts
.endproc

; Carry set if the battery holds a file that checksums.
.proc SaveValid
    ldx #3
:   lda slot_magic,x
    cmp magic,x
    bne @no
    dex
    bpl :-
    lda #<slot_data
    sta srcp
    lda #>slot_data
    sta srcp+1
    jsr SumBlock
    lda ti_sum
    cmp slot_sum
    bne @no
    lda ti_sum+1
    cmp slot_sum+1
    bne @no
    sec
    rts
@no:
    clc
    rts
.endproc

; Carry set if the file was restored into the live state.
.proc LoadGame
    jsr SaveValid
    bcs :+
    rts
:   lda #<slot_data
    sta srcp
    lda #>slot_data
    sta srcp+1
    lda #<sav_version
    sta dstp
    lda #>sav_version
    sta dstp+1
    jsr CopyBlock
    sec
    rts
.endproc

; -----------------------------------------------------------------------------
; The magic word is written as bytes, not as a string: this file has the font
; charmap applied, so "THRN" would assemble to tile indices.
magic:      .byte $54, $48, $52, $4E

s_new:      .byte "NEW GAME", STR_END
s_cont:     .byte "CONTINUE", STR_END
s_muster:   .byte "THRENOS - MUSTER", STR_END
s_pick:     .byte "PICK MEMBER", STR_END
s_empty:    .byte "-", STR_END
s_help:     .byte "A CHOOSE    B BACK", STR_END
s_ready:    .byte "THE SQUAD IS READY", STR_END
s_begin:    .byte "MAKE PLANETFALL", STR_END
s_over:     .byte "START OVER", STR_END

s_hp:       .byte "HP", STR_END
s_tp:       .byte "TP", STR_END
s_str:      .byte "STR", STR_END
s_agi:      .byte "AGI", STR_END
s_vit:      .byte "VIT", STR_END
s_spi:      .byte "SPI", STR_END

; Labels in class-record order: HP TP STR AGI VIT SPI.
stat_lbl:   .addr s_hp, s_tp, s_str, s_agi, s_vit, s_spi
