; menu.s — the field menu: START on the field opens a screen of its own with
; the party roster and the ITEM / EQUIP / TECH / STATUS pages.
; Lives in PRG bank 26 ($A000).
;
; This is not a window over the map. The map is gone while the menu is up, so
; the screen is painted with rendering off and the field is repainted by
; DrawFullMap on the way out — the same shape as BattleEnter. The "never blank
; the screen to show UI" rule is about text boxes over the field; a screen of
; its own is FF1's model, and is what this is.
;
; The drawing kit (the two-rows-a-frame pacer, page painting, numbers, table
; lookups) is src/uikit.inc, which shop.s includes as well. See its header.

.include "nes.inc"
.include "zp.inc"
.include "ram.inc"
.include "banks.inc"
.include "gen/charmap.inc"
.include "gen/dataids.inc"

.import SetPrgData, SetPrgCode, PpuAddr, PpuFill, LoadPalette
.import ScreenOff, ScreenOn, Mul8, Div8, Div16, FarCallRet
.import PutString, RowSegs, WriteRowSegs
.import ReturnToField, AddItem
.import item_tab, item_names, tech_tab, tech_names, class_names, xp_tab
.import Rederive

.export MenuOpen, MenuTick

; --- pages -------------------------------------------------------------------
P_TOP     =  0          ; roster + ITEM / EQUIP / TECH / STATUS
P_ITEM    =  1          ; the pack
P_ITEMWHO =  2          ;   ...used on whom
P_EQWHO   =  3          ; equip: whose gear
P_EQSLOT  =  4          ;   ...which slot
P_EQITEM  =  5          ;   ...with what
P_TCWHO   =  6          ; tech: whose techs
P_TCLIST  =  7          ;   ...which one
P_TCTGT   =  8          ;   ...on whom
P_STWHO   =  9          ; status: whose sheet
P_STATUS  = 10

PARTY_ROW = 3           ; roster block: member m on rows 3+3m and 4+3m
LIST_ROW  = 3           ; scrolling lists occupy rows 3..16
.ifdef TEST_LIST_N
LIST_N    = TEST_LIST_N ; test builds shrink the window so scrolling is
.else                   ; reachable without 15 things in the pack
LIST_N    = 14
.endif
OPT_ROW   = 16          ; the four top-level options
SLOT_ROW  = 6           ; WEAPON / ARMOUR / SHIELD / HELM

.segment "BANK26"

.include "uikit.inc"

; =============================================================================
; Opening, and the per-frame tick
; =============================================================================
.proc MenuOpen
    jsr UiEnter
    lda #0
    sta ui_req
    lda #P_TOP
    jmp GotoPage
.endproc

.proc MenuTick
    jsr FlushDirty
    lda pad1_new
    beq @done
    jsr ClearNote               ; any press dismisses the last notice
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
    and #BTN_START
    beq @ns
    jmp UiExit                  ; START closes the menu from any page
@ns:
    lda pad1_new
    and #BTN_A
    beq @done
    jmp PageAct
@done:
    rts
.endproc

; =============================================================================
; Page dispatch
; =============================================================================
; A = screen row -> linebuf holds that row of the current page.
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

; =============================================================================
; Shared blocks
; =============================================================================
; A = screen row: draw the roster line that belongs there, if any.
; ui_d nonzero puts the cursor next to the selected member.
.proc PartyBlock
    sec
    sbc #PARTY_ROW
    bcc @out
    cmp #12
    bcs @out
    tax
    lda k_div3,x
    sta ui_a                    ; member
    lda k_mod3,x
    sta ui_b                    ; 0 = name line, 1 = HP/TP line, 2 = blank
    lda ui_a
    cmp party_n
    bcs @out
    lda ui_b
    beq @name
    cmp #1
    beq @hp
@out:
    rts

@name:
    lda ui_d
    beq @nocur
    lda ui_a
    cmp ui_cur
    bne @nocur
    lda #TILE_CURSOR
    sta linebuf+1
@nocur:
    lda ui_a
    clc
    adc #DIGIT0+1
    sta linebuf+3
    lda ui_a
    jsr PartyOfs
    lda party+c_class,y
    jsr ClassName
    ldx #5
    jsr PutString
    lda #<s_lv
    sta ptr
    lda #>s_lv
    sta ptr+1
    ldx #19
    jsr PutString
    lda ui_a
    jsr PartyOfs
    lda party+c_level,y
    jsr Set8
    ldx #22
    jmp PutNumR

@hp:
    lda #<s_hp
    sta ptr
    lda #>s_hp
    sta ptr+1
    ldx #5
    jsr PutString
    lda ui_a
    jsr PartyOfs
    lda party+c_hp,y
    ldx party+c_hp+1,y
    jsr Set16
    ldx #11
    jsr PutNumR
    lda #SLASH
    sta linebuf+12
    lda ui_a
    jsr PartyOfs
    lda party+c_hpmax,y
    ldx party+c_hpmax+1,y
    jsr Set16
    ldx #16
    jsr PutNumR
    lda #<s_tp
    sta ptr
    lda #>s_tp
    sta ptr+1
    ldx #19
    jsr PutString
    lda ui_a
    jsr PartyOfs
    lda party+c_tp,y
    jsr Set8
    ldx #24
    jsr PutNumR
    lda #SLASH
    sta linebuf+25
    lda ui_a
    jsr PartyOfs
    lda party+c_tpmax,y
    jsr Set8
    ldx #28
    jmp PutNumR
.endproc

; The current page's heading.
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

; =============================================================================
; P_TOP
; =============================================================================
.proc EnterTop
    lda #4
    sta ui_max
    rts
.endproc

.proc RowTop
    cmp #1
    beq @credits
    cmp #OPT_ROW
    bcc @party
    cmp #OPT_ROW+4
    bcs @out
    sec
    sbc #OPT_ROW
    sta ui_a
    cmp ui_cur
    bne @nocur
    lda #TILE_CURSOR
    sta linebuf+1
@nocur:
    lda ui_a
    asl a
    tax
    lda s_topopt,x
    sta ptr
    lda s_topopt+1,x
    sta ptr+1
    ldx #3
    jmp PutString
@party:
    ldx #0
    stx ui_d
    jmp PartyBlock
@credits:
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
@out:
    rts
.endproc

.proc ActTop
    lda ui_cur
    beq @item
    cmp #1
    beq @equip
    cmp #2
    beq @tech
    lda #P_STWHO
    jmp GotoChild
@item:
    lda #P_ITEM
    jmp GotoChild
@equip:
    lda #P_EQWHO
    jmp GotoChild
@tech:
    lda #P_TCWHO
    jmp GotoChild
.endproc

; =============================================================================
; The roster pages (pick a party member)
; =============================================================================
.proc EnterWho
    lda party_n
    sta ui_max
    rts
.endproc

.proc RowWho
    cmp #1
    bne @body
    jmp TitleLine
@body:
    ldx #1
    stx ui_d
    jmp PartyBlock
.endproc

; =============================================================================
; P_ITEM — the pack
; =============================================================================
.proc EnterItem
    jmp BuildBagList
.endproc

.proc RowItem
    cmp #1
    bne @body
    jmp TitleLine
@body:
    sec
    sbc #LIST_ROW
    bcc @out
    cmp #LIST_N
    bcs @out
    clc
    adc ui_top
    cmp ui_max
    bcs @out
    sta ui_a                    ; entry index
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
    ldx #22
    jmp PutNumR
@out:
    rts
.endproc

.proc ActItem
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
    jsr ItemRec
    lda ui_rec+6                ; effect
    beq @cant                   ; gear and key items are not "used"
    cmp #5
    bcc @who                    ; 1..4: heal / cure / revive / TP
    beq @battle                 ; 5: damage-all, a battle command
    cmp #6
    beq @town                   ; 6: BEACON
    cmp #7
    beq @exit                   ; 7: EXIT CHIP
@cant:
    lda #NT_NOUSE
    jmp SetNote
@battle:
    lda #NT_BATTLE
    jmp SetNote
@who:
    lda #P_ITEMWHO
    jmp GotoChild
@town:
    lda #1
    sta ui_req
    jsr ConsumeItem
    jmp UiExit
@exit:
    lda #2
    sta ui_req
    jsr ConsumeItem
    jmp UiExit
.endproc

.proc ActItemWho
    lda ui_cur
    jsr UseItemOn
    bcc @nope
    jsr ConsumeItem
    jsr PageBack                ; back to the pack, with the count updated
    lda #NT_DONE
    jmp SetNote
@nope:
    lda #NT_NOEFFECT
    jmp SetNote
.endproc

; Use ui_item on member A. Carry set if it actually did something.
.proc UseItemOn
    sta ui_who
    lda ui_item
    jsr ItemRec
    lda ui_who
    jsr PartyOfs
    sty ui_b                    ; the member's record offset
    lda ui_rec+6
    cmp #1
    beq @heal
    cmp #2
    beq @cure
    cmp #3
    beq @revive
    cmp #4
    beq @tp
@no:
    clc
    rts

@heal:
    ldy ui_b
    lda party+c_status,y
    and #ST_DOWN
    bne @no                     ; the dead need reviving, not a medkit
    lda party+c_hp,y
    cmp party+c_hpmax,y
    bne @dohl
    lda party+c_hp+1,y
    cmp party+c_hpmax+1,y
    beq @no                     ; already at full HP
@dohl:
    ldy ui_b
    jsr HealHp
    sec
    rts

@cure:
    ldy ui_b
    lda party+c_status,y
    and #<(~ST_DOWN & $FF)
    beq @no                     ; nothing to cure
    ldy ui_b
    lda party+c_status,y
    and #ST_DOWN                ; a cure never raises the dead
    sta party+c_status,y
    sec
    rts

@revive:
    ldy ui_b
    lda party+c_status,y
    and #ST_DOWN
    beq @no
    lda party+c_status,y
    and #<(~ST_DOWN & $FF)
    sta party+c_status,y
    lda #0
    sta party+c_hp,y
    sta party+c_hp+1,y
    jsr HealHp
    sec
    rts

@tp:
    ldy ui_b
    lda party+c_tp,y
    cmp party+c_tpmax,y
    bcs @no                     ; already full
    lda party+c_tp,y
    clc
    adc ui_rec+1
    bcs @full
    cmp party+c_tpmax,y
    bcc @sett
@full:
    lda party+c_tpmax,y
@sett:
    sta party+c_tp,y
    sec
    rts
.endproc

; Y = a member's record offset: add ui_rec+1/+2 to HP, clamped to the maximum.
.proc HealHp
    lda party+c_hp,y
    clc
    adc ui_rec+1
    sta party+c_hp,y
    lda party+c_hp+1,y
    adc ui_rec+2
    sta party+c_hp+1,y
    lda party+c_hpmax+1,y
    cmp party+c_hp+1,y
    bcc @clamp
    bne @done
    lda party+c_hpmax,y
    cmp party+c_hp,y
    bcs @done
@clamp:
    lda party+c_hpmax,y
    sta party+c_hp,y
    lda party+c_hpmax+1,y
    sta party+c_hp+1,y
@done:
    rts
.endproc

.proc ConsumeItem
    ldx ui_islot
    jmp TakeOne
.endproc

; =============================================================================
; EQUIP
; =============================================================================
.proc ActEqWho
    lda ui_cur
    sta ui_who
    lda #P_EQSLOT
    jmp GotoChild
.endproc

.proc EnterEqSlot
    lda #4
    sta ui_max
    rts
.endproc

.proc RowEqSlot
    cmp #1
    beq @title
    cmp #3
    beq @derived
    sec
    sbc #SLOT_ROW
    bcc @out
    cmp #4
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
    lda s_slots,x
    sta ptr
    lda s_slots+1,x
    sta ptr+1
    ldx #3
    jsr PutString
    lda ui_who
    jsr PartyOfs
    tya
    clc
    adc ui_a
    tay
    lda party+c_weapon,y
    jsr ItemName
    ldx #12
    jmp PutString
@title:
    jsr TitleLine
    lda ui_who
    jsr PartyOfs
    lda party+c_class,y
    jsr ClassName
    ldx #10
    jmp PutString
@derived:
    lda #<s_atkdef
    sta ptr
    lda #>s_atkdef
    sta ptr+1
    ldx #3
    jsr PutString
    lda ui_who
    jsr PartyOfs
    lda party+c_atk,y
    jsr Set8
    ldx #10
    jsr PutNumR
    lda ui_who
    jsr PartyOfs
    lda party+c_def,y
    jsr Set8
    ldx #19
    jmp PutNumR
@out:
    rts
.endproc

.proc ActEqSlot
    lda ui_cur
    sta ui_slot
    lda #P_EQITEM
    jmp GotoChild
.endproc

; Everything in the pack that fits ui_slot and that ui_who's class may carry.
.proc EnterEqItem
    lda ui_who
    jsr ClassBit
    sta ui_c
    lda ui_slot
    clc
    adc #1
    sta ui_d                    ; the item kind this slot takes (1..4)
    lda #0
    sta ui_a                    ; inventory slot being examined
    sta ui_b                    ; entries found so far
@lp:
    ldx ui_a
    lda inv_id,x
    beq @next
    lda inv_ct,x
    beq @next
    ldx ui_a
    lda inv_id,x
    jsr ItemRec
    lda ui_rec+0
    cmp ui_d
    bne @next
    lda ui_rec+5                ; equip mask
    and ui_c
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

.proc RowEqItem
    cmp #1
    beq @title
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
    lda ui_rec+1                ; its power, so the swap can be judged
    jsr Set8
    ldx #22
    jmp PutNumR
@title:
    jsr TitleLine
    lda ui_slot
    asl a
    tax
    lda s_slots,x
    sta ptr
    lda s_slots+1,x
    sta ptr+1
    ldx #10
    jmp PutString
@out:
    rts
.endproc

.proc ActEqItem
    lda ui_max
    bne @go
    rts
@go:
    ldx ui_cur
    lda ui_list,x
    sta ui_item
    lda ui_lidx,x
    sta ui_islot
    lda ui_who                  ; the record byte this slot lives in
    jsr PartyOfs
    tya
    clc
    adc ui_slot
    tay
    sty ui_e
    lda party+c_weapon,y
    beq @free
    ldy #1
    jsr AddItem                 ; the displaced piece goes back in the pack
    bcc @free                   ; FIRST: with no room, nothing changes at all
    lda #NT_NOROOM
    jmp SetNote
@free:
    ldx ui_islot
    jsr TakeOne
    ldy ui_e
    lda ui_item
    sta party+c_weapon,y
    ; the stat formula lives in the battle bank; call it, never copy it
    lda #<Rederive
    sta ptr
    lda #>Rederive
    sta ptr+1
    lda #BATTLE_BANK
    sta far_bank
    lda ui_who
    jsr FarCallRet
    jsr PageBack                ; back to the slot list, with the new gear on
    lda #NT_EQUIPPED
    jmp SetNote
.endproc

; =============================================================================
; TECH
; =============================================================================
.proc ActTcWho
    lda ui_cur
    sta ui_who
    lda #P_TCLIST
    jmp GotoChild
.endproc

; The techs ui_who knows: two 16-bit masks, PSI 0..15 then BIO 16..31.
.proc EnterTcList
    lda ui_who
    jsr PartyOfs
    lda party+c_psi,y
    sta ui_a
    lda party+c_psi+1,y
    sta ui_b
    lda party+c_bio,y
    sta ui_c
    lda party+c_bio+1,y
    sta ui_d
    ldx #0
    lda #0
    sta ui_e
@lp:
    lda ui_e
    cmp #16
    bcs @bio
    cmp #8
    bcs @psihi
    tay
    lda ui_a
    jmp @test
@psihi:
    sec
    sbc #8
    tay
    lda ui_b
    jmp @test
@bio:
    sec
    sbc #16
    cmp #8
    bcs @biohi
    tay
    lda ui_c
    jmp @test
@biohi:
    sec
    sbc #8
    tay
    lda ui_d
@test:
    cpy #0
    beq @have
@sh:
    lsr a
    dey
    bne @sh
@have:
    and #1
    beq @next
    lda ui_e
    sta ui_list,x
    inx
    cpx #32
    bcs @done
@next:
    inc ui_e
    lda ui_e
    cmp #32
    bcc @lp
@done:
    stx ui_max
    rts
.endproc

.proc RowTcList
    cmp #1
    beq @title
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
    jsr TechName
    ldx #3
    jsr PutString
    lda #<s_tp
    sta ptr
    lda #>s_tp
    sta ptr+1
    ldx #18
    jsr PutString
    ldx ui_a
    lda ui_list,x
    jsr TechRec
    lda ui_trec+1               ; the tier doubles as the TP cost
    jsr Set8
    ldx #23
    jmp PutNumR
@title:
    jsr TitleLine
    lda ui_who
    jsr PartyOfs
    lda party+c_class,y
    jsr ClassName
    ldx #9
    jmp PutString
@out:
    rts
.endproc

.proc ActTcList
    lda ui_max
    bne @go
    rts
@go:
    ldx ui_cur
    lda ui_list,x
    sta ui_tech
    jsr TechRec
    lda ui_trec+0
    cmp #2                      ; only BIO support works outside a fight
    bne @battle
    lda ui_trec+2
    ora ui_trec+5
    beq @battle                 ; no heal and no cure: nothing it can do here
    lda ui_who
    jsr PartyOfs
    lda party+c_tp,y
    cmp ui_trec+1
    bcc @notp
    lda ui_trec+4
    cmp #3                      ; TG_ALL_ALLY: there is no target to pick
    bne @one
    jsr SpendTp
    lda #0
    sta ui_e
@all:
    lda ui_e
    jsr TechHeal
    inc ui_e
    lda ui_e
    cmp party_n
    bcc @all
    jsr RefreshPage
    lda #NT_DONE
    jmp SetNote
@one:
    lda #P_TCTGT
    jmp GotoChild
@battle:
    lda #NT_BATTLE
    jmp SetNote
@notp:
    lda #NT_NOTP
    jmp SetNote
.endproc

.proc ActTcTgt
    lda ui_who
    jsr PartyOfs
    lda party+c_tp,y
    cmp ui_trec+1
    bcc @notp
    lda ui_cur                  ; try it first: a cure with nothing to cure,
    jsr TechHeal                ; or a heal on someone already full, must not
    bcc @noeffect               ; cost TP -- the ITEM page already works this way
    jsr SpendTp
    jsr PageBack
    lda #NT_DONE
    jmp SetNote
@noeffect:
    lda #NT_NOEFFECT
    jmp SetNote
@notp:
    lda #NT_NOTP
    jmp SetNote
.endproc

.proc SpendTp
    lda ui_who
    jsr PartyOfs
    lda party+c_tp,y
    sec
    sbc ui_trec+1
    sta party+c_tp,y
    rts
.endproc

; A = member: apply the current tech's cure and healing to them.
; Carry set if anything actually changed, so the caller can refuse to charge TP
; for a cure with nothing to cure. It used to wipe every status bit whatever the
; tech's mask said, which made CLEANSE (poison only) as good as PURGE.
.proc TechHeal
    jsr PartyOfs
    sty ui_b
    lda #0
    sta ui_c                    ; how many things this did

    lda ui_trec+5               ; the status bits this tech cures
    beq @heal
    and #<(~ST_DOWN & $FF)      ; no mask ever raises the dead
    sta ui_d
    ldy ui_b
    and party+c_status,y
    beq @heal                   ; none of them are set on this member
    lda ui_d
    eor #$FF
    and party+c_status,y
    sta party+c_status,y
    inc ui_c

@heal:
    lda ui_trec+2               ; healing power
    beq @done
    sta ui_rec+1
    lda #0
    sta ui_rec+2
    ldy ui_b
    lda party+c_status,y
    and #ST_DOWN
    bne @done                   ; a plain heal does not raise the dead
    lda party+c_hp,y
    cmp party+c_hpmax,y
    bne @dohl
    lda party+c_hp+1,y
    cmp party+c_hpmax+1,y
    beq @done                   ; already at full HP
@dohl:
    ldy ui_b
    jsr HealHp
    inc ui_c
@done:
    lda ui_c
    beq @nothing
    sec
    rts
@nothing:
    clc
    rts
.endproc

; =============================================================================
; STATUS
; =============================================================================
.proc ActStWho
    lda ui_cur
    sta ui_who
    lda #P_STATUS
    jmp GotoChild
.endproc

.proc EnterStatus
    lda #0
    sta ui_max
    rts
.endproc

.proc ActStatus
    rts
.endproc

.proc RowStatus
    sta ui_e                    ; the row, kept for the tail of this routine
    cmp #1
    bne @n1
    jmp @title
@n1:
    cmp #3
    bne @n3
    jmp @class
@n3:
    cmp #4
    bne @n4
    jmp @vet
@n4:
    cmp #6
    bne @n6
    jmp @xp
@n6:
    cmp #7
    bne @n7
    jmp @next
@n7:
    cmp #9
    bne @n9
    jmp @hp
@n9:
    cmp #11
    bcs @n11
    rts
@n11:
    cmp #15
    bcs @n15
    jmp @stats
@n15:
    cmp #17
    bcs @n17
    rts
@n17:
    cmp #21
    bcc @g
    rts
@g:
    jmp @gear

@title:
    jmp TitleLine

@class:
    lda ui_who
    jsr PartyOfs
    lda party+c_class,y
    jsr ClassName
    ldx #2
    jsr PutString
    lda #<s_lv
    sta ptr
    lda #>s_lv
    sta ptr+1
    ldx #17
    jsr PutString
    lda ui_who
    jsr PartyOfs
    lda party+c_level,y
    jsr Set8
    ldx #22
    jmp PutNumR

@vet:
    lda ui_who
    jsr PartyOfs
    lda party+c_class,y
    asl a
    tax
    lda s_vets,x
    sta ptr
    lda s_vets+1,x
    sta ptr+1
    ldx #2
    jmp PutString

@xp:
    lda #<s_xp
    sta ptr
    lda #>s_xp
    sta ptr+1
    ldx #2
    jsr PutString
    lda ui_who
    jsr PartyOfs
    lda party+c_xp,y
    sta ui_n24
    lda party+c_xp+1,y
    sta ui_n24+1
    lda party+c_xp+2,y
    sta ui_n24+2
    ldx #22
    jmp PutNumR

@next:
    lda #<s_next
    sta ptr
    lda #>s_next
    sta ptr+1
    ldx #2
    jsr PutString
    jsr NextXp
    ldx #22
    jmp PutNumR

@hp:
    lda #<s_hp
    sta ptr
    lda #>s_hp
    sta ptr+1
    ldx #2
    jsr PutString
    lda ui_who
    jsr PartyOfs
    lda party+c_hp,y
    ldx party+c_hp+1,y
    jsr Set16
    ldx #9
    jsr PutNumR
    lda #SLASH
    sta linebuf+10
    lda ui_who
    jsr PartyOfs
    lda party+c_hpmax,y
    ldx party+c_hpmax+1,y
    jsr Set16
    ldx #14
    jsr PutNumR
    lda #<s_tp
    sta ptr
    lda #>s_tp
    sta ptr+1
    ldx #18
    jsr PutString
    lda ui_who
    jsr PartyOfs
    lda party+c_tp,y
    jsr Set8
    ldx #23
    jsr PutNumR
    lda #SLASH
    sta linebuf+24
    lda ui_who
    jsr PartyOfs
    lda party+c_tpmax,y
    jsr Set8
    ldx #27
    jmp PutNumR

; rows 11..14: STR/AGI, VIT/SPI, ATK/DEF, EVA/HIT
@stats:
    sec
    sbc #11
    asl a
    sta ui_a                    ; first of the pair
    lda #0
    sta ui_b                    ; 0 = left half, 1 = right half
@sl:
    lda ui_a
    asl a
    tax
    lda k_statnm,x
    sta ptr
    lda k_statnm+1,x
    sta ptr+1
    ldx #2
    lda ui_b
    beq @sl1
    ldx #16
@sl1:
    jsr PutString
    ldx ui_a
    lda k_statof,x
    sta ui_c
    lda ui_who
    jsr PartyOfs
    tya
    clc
    adc ui_c
    tay
    lda party,y
    jsr Set8
    ldx #10
    lda ui_b
    beq @sl2
    ldx #24
@sl2:
    jsr PutNumR
    inc ui_a
    inc ui_b
    lda ui_b
    cmp #2
    bcc @sl
    rts

; rows 17..20: the four equipped pieces
@gear:
    lda ui_e
    sec
    sbc #17
    sta ui_a
    asl a
    tax
    lda s_slots,x
    sta ptr
    lda s_slots+1,x
    sta ptr+1
    ldx #2
    jsr PutString
    lda ui_who
    jsr PartyOfs
    tya
    clc
    adc ui_a
    tay
    lda party+c_weapon,y
    jsr ItemName
    ldx #11
    jmp PutString
@out:
    rts
.endproc

; The XP needed to reach the next level -> ui_n24 (0 once capped).
.proc NextXp
    lda ui_who
    jsr PartyOfs
    lda party+c_level,y
    cmp #30
    bcc @ok
    lda #0
    jmp Set8
@ok:
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
    ldy #0
    lda (srcp),y
    sta ui_n24
    iny
    lda (srcp),y
    sta ui_n24+1
    iny
    lda (srcp),y
    sta ui_n24+2
    rts
.endproc

; A = tech id -> ptr = its name
.proc TechName
    jsr NamePtr
    lda mul_res
    clc
    adc #<tech_names
    sta ptr
    lda mul_res+1
    adc #>tech_names
    sta ptr+1
    rts
.endproc

; A = tech id -> ui_trec = its record (school, tier/TP, power, element,
; target, status mask)
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
@lp:
    lda (srcp),y
    sta ui_trec,y
    iny
    cpy #TECH_REC
    bne @lp
    rts
.endproc

; =============================================================================
; Tables
; =============================================================================
comp_l:
    .byte <RowTop, <RowItem, <RowWho, <RowWho, <RowEqSlot, <RowEqItem
    .byte <RowWho, <RowTcList, <RowWho, <RowWho, <RowStatus
comp_h:
    .byte >RowTop, >RowItem, >RowWho, >RowWho, >RowEqSlot, >RowEqItem
    .byte >RowWho, >RowTcList, >RowWho, >RowWho, >RowStatus

ente_l:
    .byte <EnterTop, <EnterItem, <EnterWho, <EnterWho, <EnterEqSlot
    .byte <EnterEqItem, <EnterWho, <EnterTcList, <EnterWho, <EnterWho
    .byte <EnterStatus
ente_h:
    .byte >EnterTop, >EnterItem, >EnterWho, >EnterWho, >EnterEqSlot
    .byte >EnterEqItem, >EnterWho, >EnterTcList, >EnterWho, >EnterWho
    .byte >EnterStatus

acti_l:
    .byte <ActTop, <ActItem, <ActItemWho, <ActEqWho, <ActEqSlot, <ActEqItem
    .byte <ActTcWho, <ActTcList, <ActTcTgt, <ActStWho, <ActStatus
acti_h:
    .byte >ActTop, >ActItem, >ActItemWho, >ActEqWho, >ActEqSlot, >ActEqItem
    .byte >ActTcWho, >ActTcList, >ActTcTgt, >ActStWho, >ActStatus

;         TOP ITEM IWHO EQWHO ESLOT EITEM TCWHO TCLST TCTGT STWHO STATUS
pg_row0: .byte 16,  3,   3,    3,    6,    3,    3,    3,    3,    3,    0
pg_step: .byte  1,  1,   3,    3,    1,    1,    3,    1,    3,    3,    1
pg_rows: .byte  4, LIST_N, 4,   4,    4, LIST_N,  4, LIST_N,  4,   4,    1
pg_back: .byte $FF, 0,   1,    0,    3,    4,    0,    6,    7,    0,    9

pg_title:
    .addr s_t_top, s_t_item, s_t_use, s_t_equip, s_t_equip, s_t_equip
    .addr s_t_tech, s_t_tech, s_t_heal, s_t_status, s_t_status

k_div3:  .byte 0,0,0, 1,1,1, 2,2,2, 3,3,3
k_mod3:  .byte 0,1,2, 0,1,2, 0,1,2, 0,1,2

k_statnm: .addr s_str, s_agi, s_vit, s_spi, s_atk, s_def, s_eva, s_hit
k_statof: .byte c_str, c_agi, c_vit, c_spi, c_atk, c_def, c_eva, c_hit

s_credits: .byte "CREDITS", STR_END
s_lv:      .byte "LV", STR_END
s_hp:      .byte "HP", STR_END
s_tp:      .byte "TP", STR_END
s_xp:      .byte "XP", STR_END
s_next:    .byte "NEXT LEVEL", STR_END
s_atkdef:  .byte "ATK      DEF", STR_END

s_topopt:  .addr s_o_item, s_o_equip, s_o_tech, s_o_status
s_o_item:   .byte "ITEM", STR_END
s_o_equip:  .byte "EQUIP", STR_END
s_o_tech:   .byte "TECH", STR_END
s_o_status: .byte "STATUS", STR_END

s_slots:   .addr s_s_wpn, s_s_arm, s_s_shd, s_s_hlm
s_s_wpn:   .byte "WEAPON", STR_END
s_s_arm:   .byte "ARMOUR", STR_END
s_s_shd:   .byte "SHIELD", STR_END
s_s_hlm:   .byte "HELM", STR_END

s_t_top:    .byte "PARTY", STR_END
s_t_item:   .byte "ITEM", STR_END
s_t_use:    .byte "USE ON WHOM", STR_END
s_t_equip:  .byte "EQUIP", STR_END
s_t_tech:   .byte "TECH", STR_END
s_t_heal:   .byte "ON WHOM", STR_END
s_t_status: .byte "STATUS", STR_END

s_str:     .byte "STR", STR_END
s_agi:     .byte "AGI", STR_END
s_vit:     .byte "VIT", STR_END
s_spi:     .byte "SPI", STR_END
s_atk:     .byte "ATK", STR_END
s_def:     .byte "DEF", STR_END
s_eva:     .byte "EVA", STR_END
s_hit:     .byte "HIT", STR_END

; The veteran titles belong with the rest of the class data, but the generator
; (tools/emit_data.py) does not emit them yet and is owned elsewhere; this is a
; copy of the last column of gamedata.CLASSES and must be kept in step with it.
s_vets:    .addr s_v0, s_v1, s_v2, s_v3, s_v4, s_v5
s_v0:      .byte "VANGUARD", STR_END
s_v1:      .byte "MARKSMAN", STR_END
s_v2:      .byte "SURGEON", STR_END
s_v3:      .byte "ORACLE", STR_END
s_v4:      .byte "ARTIFICER", STR_END
s_v5:      .byte "MYRMIDON", STR_END
