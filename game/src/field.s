; field.s — the map/field engine: data-driven maps, two-axis scrolling with
; row and column streaming, grid-locked movement and collision.
; Lives in PRG bank 30 ($C000, always mapped).

.include "nes.inc"
.include "zp.inc"
.include "ram.inc"
.include "banks.inc"
.include "gen/charmap.inc"
.include "gen/msgids.inc"
.include "gen/dataids.inc"
.include "gen/songids.inc"

.import SetPrgData, SetChrBank, PpuAddr, PpuFill, LoadPalette, Random
.import Div8, VBufAlloc, ScreenOff, ScreenOn, ClearNametables
.import map_bank_tab, map_addr_tab, tset_bank_tab, tset_addr_tab
.import spr_palette

.export GameInit, GameFrame
.export LoadMap, DecodeRow, CellAt, DrawFullMap, UpdateCamera
.export CellProp, RowSlot, BuildRowStrip, AttrRowShadow, AttrRowForce
.export QueueAttrRow, SyncHeroPixels
.import SetMessage, OpenBox, CloseBox, BoxStep, RenderLine
.import DrawPrompt, ClearPrompt, RowSegs, WriteRowSegs, FillRowSegs
.import BattleEnter, BattleTick, InitParty, RollEncounter
.import PutNumber, PutString, Mul8
.import item_names, boss_by_map
.import SetPrgCode

DIR_UP    = 0
DIR_DOWN  = 1
DIR_LEFT  = 2
DIR_RIGHT = 3

ST_IDLE   = 0
ST_MOVE   = 1

MOVE_SPEED = 2                  ; pixels per frame (16px cell = 8 frames)

HERO_SX   = 120                 ; hero's fixed screen position
HERO_SY   = 112

GS_FIELD    = 0
GS_BOXOPEN  = 1
GS_TEXT     = 2
GS_TEXTWAIT = 3
GS_DIALOG   = 4
GS_BOXCLOSE = 5
GS_BATTLE   = 6
GS_GAMEOVER = 7
GS_ENDED    = 8

TEXT_ROW0   = 21
TEXT_LINES  = 4

; map object kinds (must match tools/maps.py)
OB_NPC   = 1
OB_CHEST = 2
OB_WARP  = 3
OB_SIGN  = 4
OB_SHOP  = 5
OB_INN   = 6
OB_SAVE  = 7
OB_TRIG  = 8

.segment "ENGINE"

; =============================================================================
; Boot
; =============================================================================
.proc GameInit
    lda #$FF
    sta mrow_id0
    lda #0
    sta gamestate
    sta game_flags
    jsr InitStoryState

    lda #BATTLE_BANK
    jsr SetPrgCode
    jsr InitParty

.ifdef TEST_START_DUNGEON
    lda #TEST_START_DUNGEON     ; test builds boot straight into a map
    jsr LoadMap
.ifdef TEST_START_X
    lda #TEST_START_X           ; ...optionally at a chosen cell, so a test can
    sta ent_gx                  ; exercise one object without a long walk
    lda #TEST_START_Y
    sta ent_gy
.else
    lda #12                     ; every area map is entered at (12,18)
    sta ent_gx
    lda #18
    sta ent_gy
.endif
.else
    lda #0                      ; the overworld
    jsr LoadMap
    lda #44                     ; START position (see tools/world.py)
    sta ent_gx
    lda #68
    sta ent_gy
.endif
    lda #DIR_DOWN
    sta ent_dir
    lda #ST_IDLE
    sta ent_state
    jsr SyncHeroPixels
    jsr UpdateCamera
    jsr DrawFullMap
    rts
.endproc

.proc InitStoryState
    lda #$FF
    sta pend_form
    sta pend_flag
    lda #0
    sta msg_chain
    sta box_ctx
    rts
.endproc

; The ending: MSG_END_1..7 are consecutive, so one chained message covers it.
.proc StartEnding
    lda #SONG_ENDING
    sta music_req
    lda #1
    sta box_ctx
    ldx #6                      ; MSG_END_1 plus six more
    lda #MSG_END_1
    jmp ShowMessageChain
.endproc

; A = first message id, X = how many consecutive ids follow it.
; The count needs its own byte: SetMessage uses tmpa as scratch, so stashing it
; there made the chain length come back as the message id.
.proc ShowMessageChain
    stx chain_n
    jsr ShowMessage
    lda chain_n
    sta msg_chain
    rts
.endproc

; Nothing follows the ending: hold the last frame.
.proc StEnded
    jmp BuildOAM
.endproc

; =============================================================================
; Per-frame: dispatch on gamestate through an RTS jump table
; =============================================================================
.proc GameFrame
    lda gamestate
    asl a
    tax
    lda state_tab+1,x
    pha
    lda state_tab,x
    pha
    rts
.endproc

; --- GS_FIELD: walking -------------------------------------------------------
.proc StField
    jsr UpdateHero
    jsr UpdateCamera            ; ALWAYS: a trigger or encounter fired by the
                                ; landing step leaves the camera one frame
                                ; stale, and every window's geometry is
                                ; computed from cam_tx/cam_ty
    lda gamestate               ; UpdateHero may have started a battle or a
    cmp #GS_FIELD               ; warp: the rest of this state must not run
    beq :+
    rts
:
    jsr StreamCheck
    jsr BuildOAM
    lda ent_state
    bne @done                   ; only act when grid-aligned
    lda pad1_new
    and #BTN_A
    beq @done
    jsr TalkOrAct
@done:
    rts
.endproc

; --- GS_BOXOPEN / GS_BOXCLOSE: run the window job ---------------------------
.proc StBoxOpen
    jsr BoxStep
    jsr BuildOAM
    lda box_done
    beq @done
    lda #0
    sta cur_line
    lda #GS_TEXT
    sta gamestate
@done:
    rts
.endproc

.proc StBoxClose
    jsr BoxStep
    jsr BuildOAM
    lda box_done
    beq @done
    lda box_ctx
    cmp #1                      ; the ending: nothing follows it
    bne :+
    lda #GS_ENDED
    sta gamestate
    rts
:   lda #GS_FIELD
    sta gamestate
    lda pend_form               ; a trigger armed a boss: fight it now
    cmp #$FF
    beq @done
    pha
    lda #$FF
    sta pend_form
    lda #GS_BATTLE
    sta gamestate
    lda #BATTLE_BANK
    jsr SetPrgCode
    pla
    jsr BattleEnter
@done:
    rts
.endproc

; --- GS_TEXT: one line per frame --------------------------------------------
.proc StText
    jsr BuildOAM
    jsr RenderLine
    lda cur_line
    clc
    adc #TEXT_ROW0
    jsr RowSegs
    jsr WriteRowSegs
    inc cur_line
    lda term_action
    cmp #2
    beq @end
    cmp #1
    beq @page
    lda cur_line
    cmp #TEXT_LINES
    bcc @done
@page:
    lda #GS_TEXTWAIT
    sta gamestate
    jsr DrawPrompt
    rts
@end:
    lda #GS_DIALOG
    sta gamestate
@done:
    rts
.endproc

; --- GS_TEXTWAIT: page full, waiting for A ----------------------------------
.proc StTextWait
    jsr BuildOAM
    lda pad1_new
    and #BTN_A
    beq @done
    jsr ClearPrompt
    lda #0
    sta cur_line
    lda #GS_TEXT
    sta gamestate
    jsr BlankInterior
@done:
    rts
.endproc

; --- GS_DIALOG: message finished, waiting for A -----------------------------
.proc StDialog
    jsr BuildOAM
    lda pend_kind
    beq @wait
    jsr DrawPendLine
@wait:
    lda pad1_new
    and #BTN_A
    beq @done
    lda msg_chain
    beq @close
    dec msg_chain               ; more of this scene to read
    inc msg_id
    lda msg_id
    jsr SetMessage
    lda #0
    sta cur_line
    jsr BlankInterior
    lda #GS_TEXT
    sta gamestate
    rts
@close:
    jsr CloseBox
    lda #GS_BOXCLOSE
    sta gamestate
@done:
    rts
.endproc

; Blank the four interior lines (they are redrawn line by line).
; Write "<n> CREDITS" or an item's name on the message's second line, so a
; chest tells you what you actually got.
.proc DrawPendLine
    lda pend_kind
    sta tmpd
    lda #0
    sta pend_kind
    ldx #0
    lda #0
:   sta linebuf,x
    inx
    cpx #32
    bne :-
    lda #TILE_FRAME+3
    sta linebuf
    lda #TILE_FRAME+5
    sta linebuf+31
    lda tmpd
    cmp #2
    beq @item
    lda pend_lo
    sta num_lo
    lda pend_hi
    sta num_hi
    ldx #4
    jsr PutNumber
    inx
    lda #<s_credits
    sta ptr
    lda #>s_credits
    sta ptr+1
    jsr PutString
    jmp @put
@item:
    lda #BANK_TABLES
    jsr SetPrgData
    lda pend_item
    sta mul_a
    lda #NAME_LEN
    sta mul_b
    jsr Mul8
    lda mul_res
    clc
    adc #<item_names
    sta ptr
    lda mul_res+1
    adc #>item_names
    sta ptr+1
    ldx #4
    jsr PutString
@put:
    lda #TEXT_ROW0+1
    jsr RowSegs
    jsr WriteRowSegs
    lda map_bank                ; put the map's bank back under $8000
    jmp SetPrgData
.endproc

.proc BlankInterior
    lda #TEXT_ROW0
    sta box_row_i
    lda #TEXT_LINES
    sta box_cnt
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

; =============================================================================
; Interaction: A in the field
; =============================================================================
; Look at the cell the leader faces; talk to an NPC or read a sign there.
.proc TalkOrAct
    lda ent_gx
    sta tgt_gx
    lda ent_gy
    sta tgt_gy
    lda ent_dir
    cmp #DIR_UP
    bne :+
    dec tgt_gy
    jmp @scan
:   cmp #DIR_DOWN
    bne :+
    inc tgt_gy
    jmp @scan
:   cmp #DIR_LEFT
    bne :+
    dec tgt_gx
    jmp @scan
:   inc tgt_gx
@scan:
    jsr FindObject
    bcs @found
    ; nothing in front: a chest may be under our own feet (they sit on
    ; walkable cells, so the party can be standing on one)
    lda ent_gx
    sta tgt_gx
    lda ent_gy
    sta tgt_gy
    jsr FindObject
    bcc @nobody
@found:
    ldx obj_i
    lda ent_kind,x
    cmp #OB_NPC
    beq @talk
    cmp #OB_SIGN
    beq @talk
    cmp #OB_SAVE
    beq @talk
    cmp #OB_CHEST
    beq @chest
    cmp #OB_INN
    beq @inn
@nobody:
    lda #MSG_SYS_NOTHING
    jmp ShowMessage
@talk:
    lda ent_arg,x
    jmp ShowMessage
@chest:
    jmp OpenChest
@inn:
    jmp UseInn
.endproc

; =============================================================================
; Inns
; =============================================================================
; X = the inn's entity slot. a0/a1 = price, a2 = the innkeeper's message.
; Resting restores every member to full HP and TP and clears their status.
.proc UseInn
    lda ent_tile,x              ; price low
    sta pend_lo
    lda ent_dir,x               ; price high
    sta pend_hi
    lda credits+2               ; afford it? (24-bit purse vs 16-bit price)
    bne @afford
    lda credits+1
    cmp pend_hi
    bcc @poor
    bne @afford
    lda credits
    cmp pend_lo
    bcc @poor
@afford:
    lda credits
    sec
    sbc pend_lo
    sta credits
    lda credits+1
    sbc pend_hi
    sta credits+1
    lda credits+2
    sbc #0
    sta credits+2
    jsr RestParty
    lda #SFX_HEAL
    sta sfx_req
    lda #1                      ; the second line shows what it cost
    sta pend_kind
    lda #MSG_SYS_REST_DONE
    jmp ShowMessage
@poor:
    lda #0
    sta pend_kind
    lda #MSG_SYS_NO_CREDITS
    jmp ShowMessage
.endproc

.proc RestParty
    ldx #0
@lp:
    txa
    asl a
    asl a
    asl a
    asl a
    asl a
    tay
    lda party+c_hpmax,y
    sta party+c_hp,y
    lda party+c_hpmax+1,y
    sta party+c_hp+1,y
    lda party+c_tpmax,y
    sta party+c_tp,y
    lda #0
    sta party+c_status,y
    inx
    cpx #4
    bcc @lp
    rts
.endproc

; =============================================================================
; Story triggers
; =============================================================================
; Stepping onto an OB_TRIG whose story flag is still clear plays its scene.
; If the map has a boss (boss_by_map), the trigger arms it: the fight starts
; when the message window closes, and the flag is set only once it is won, so
; losing or reloading leaves the trigger armed.
.proc CheckTrigger
    lda ent_gx
    sta tgt_gx
    lda ent_gy
    sta tgt_gy
    jsr FindObject
    bcc @none
    ldx obj_i
    lda ent_kind,x
    cmp #OB_TRIG
    bne @none
    lda ent_tile,x              ; a0 = story flag id
    sta tmpa
    jsr StoryFlagSet
    bcs @none                   ; already played
    ldx map_id
    lda boss_by_map,x
    sta pend_form               ; $FF when this map has no boss
    cmp #$FF
    beq @noboss
    lda tmpa
    sta pend_flag               ; set once the fight is won
    jmp @say
@noboss:
    lda #$FF
    sta pend_flag
    lda tmpa                    ; a scene with no fight: mark it seen now
    jsr MarkStory
@say:
    ldx obj_i
    lda ent_arg,x               ; a2 = the scene's message
    jmp ShowMessage
@none:
    rts
.endproc

; A = story flag id -> carry set if it has already happened.
.proc StoryFlagSet
    pha
    lsr a
    lsr a
    lsr a
    tay
    pla
    and #7
    tax
    lda story_flags,y
    and bit_tab,x
    beq @no
    sec
    rts
@no:
    clc
    rts
.endproc

; A = story flag id: record it.
.proc MarkStory
    pha
    lsr a
    lsr a
    lsr a
    tay
    pla
    and #7
    tax
    lda story_flags,y
    ora bit_tab,x
    sta story_flags,y
    rts
.endproc

; =============================================================================
; Treasure chests
; =============================================================================
; X = the chest's entity slot. Object bytes are
;   a0 = chest flag id, a1 = item id, a2 = count, a3/a4 = credits.
.proc OpenChest
    lda #0
    sta pend_kind
    lda ent_tile,x              ; flag id
    sta tmpa
    jsr ChestFlagSet
    bcc @fresh
    lda #MSG_SYS_CHEST_ALREADY
    jmp ShowMessage
@fresh:
    lda tmpa
    jsr MarkChestTaken
    ldx obj_i
    lda ent_dir,x               ; item id
    beq @credits
    sta pend_item
    ldy ent_arg,x               ; count
    bne :+
    ldy #1
:   jsr AddItem
    bcs @full
    lda #2
    sta pend_kind
    lda #MSG_SYS_GOT_ITEM
    jmp ShowMessage
@full:
    lda #MSG_SYS_CARRY_FULL
    jmp ShowMessage
@credits:
    lda ent_home,x              ; credits low
    sta pend_lo
    lda ent_a4,x                ; credits high
    sta pend_hi
    jsr AddCredits
    lda pend_lo
    ora pend_hi
    beq @empty
    lda #1
    sta pend_kind
    lda #MSG_SYS_GOT_CREDITS
    jmp ShowMessage
@empty:
    lda #MSG_SYS_CHEST_EMPTY
    jmp ShowMessage
.endproc

; A = chest flag id -> carry set if that chest has already been opened.
.proc ChestFlagSet
    pha
    lsr a
    lsr a
    lsr a
    tay                         ; byte index
    pla
    and #7
    tax
    lda chest_flags,y
    and bit_tab,x
    beq @no
    sec
    rts
@no:
    clc
    rts
.endproc

; A = chest flag id: record it as opened (the save file remembers).
.proc MarkChestTaken
    pha
    lsr a
    lsr a
    lsr a
    tay
    pla
    and #7
    tax
    lda chest_flags,y
    ora bit_tab,x
    sta chest_flags,y
    rts
.endproc

; A = item id, Y = count. Carry set if the inventory is full.
.proc AddItem
    sta tmpb
    sty tmpc
    ldx #0
@stack:
    lda inv_id,x
    cmp tmpb
    bne @nextstack
    lda inv_ct,x
    clc
    adc tmpc
    cmp #100
    bcs @nextstack              ; would overflow the stack: use a new slot
    sta inv_ct,x
    clc
    rts
@nextstack:
    inx
    cpx #32
    bcc @stack
    ldx #0
@free:
    lda inv_id,x
    beq @put
    inx
    cpx #32
    bcc @free
    sec
    rts
@put:
    lda tmpb
    sta inv_id,x
    lda tmpc
    sta inv_ct,x
    clc
    rts
.endproc

; pend_lo/pend_hi credits into the party's purse (24-bit, saturating).
.proc AddCredits
    lda credits
    clc
    adc pend_lo
    sta credits
    lda credits+1
    adc pend_hi
    sta credits+1
    lda credits+2
    adc #0
    sta credits+2
    bcc @done
    lda #$FF                    ; saturate rather than wrap
    sta credits
    sta credits+1
    sta credits+2
@done:
    rts
.endproc

; A = message id: open the window and start the message. Messages shown this
; way can be chained (see msg_chain) because the script's ids are consecutive.
.proc ShowMessage
    sta msg_id
    ldx #0
    stx msg_chain               ; a plain message never inherits a stale chain
    jsr SetMessage
    jsr OpenBox
    lda #GS_BOXOPEN
    sta gamestate
    rts
.endproc

; Find a map object at (tgt_gx, tgt_gy). Carry set = found, obj_i = its slot.
.proc FindObject
    ldx #1
@lp:
    cpx ent_count
    bcs @none
    lda ent_kind,x
    beq @next
    lda ent_gx,x
    cmp tgt_gx
    bne @next
    lda ent_gy,x
    cmp tgt_gy
    bne @next
    stx obj_i
    sec
    rts
@next:
    inx
    bne @lp
@none:
    clc
    rts
.endproc

; =============================================================================
; Warps
; =============================================================================
; Called when the leader lands on a new cell.
.proc CheckWarp
    lda ent_gx
    sta tgt_gx
    lda ent_gy
    sta tgt_gy
    jsr FindObject
    bcc @none
    ldx obj_i
    lda ent_kind,x
    cmp #OB_WARP
    bne @none
    lda ent_tile,x              ; a0 = destination map
    pha
    lda ent_dir,x               ; a1 = destination gx
    sta tmpa
    lda ent_arg,x               ; a2 = destination gy
    sta tmpb
    pla
    jsr DoWarp
@none:
    rts
.endproc

; A = destination map, tmpa/tmpb = destination cell.
.proc DoWarp
    jsr LoadMap
    lda tmpa
    sta ent_gx
    lda tmpb
    sta ent_gy
    lda #ST_IDLE
    sta ent_state
    jsr SyncHeroPixels
    jsr UpdateCamera
    jsr DrawFullMap
    rts
.endproc


; =============================================================================
; Map loading
; =============================================================================
; A = map id.
.proc LoadMap
    sta map_id
    tax
    lda map_bank_tab,x
    sta map_bank
    jsr SetPrgData
    txa
    asl a
    tay
    lda map_addr_tab,y
    sta mt_ptr
    lda map_addr_tab+1,y
    sta mt_ptr+1

    ldy #0
    lda (mt_ptr),y
    sta map_w
    iny
    lda (mt_ptr),y
    sta map_h
    iny
    lda (mt_ptr),y
    pha                         ; tileset id
    iny
    lda (mt_ptr),y
    sta map_music
    sta music_req               ; the driver picks this up on the next tick
    iny
    lda (mt_ptr),y
    sta enc_tab
    iny
    lda (mt_ptr),y
    sta enc_rate
    iny
    lda (mt_ptr),y
    sta map_flags
    iny
    lda (mt_ptr),y
    sta map_objn
    iny
    lda (mt_ptr),y
    sta map_rowtab
    iny
    lda (mt_ptr),y
    sta map_rowtab+1
    iny
    lda (mt_ptr),y
    sta map_objs
    iny
    lda (mt_ptr),y
    sta map_objs+1
    iny
    lda (mt_ptr),y
    sta map_zones
    iny
    lda (mt_ptr),y
    sta map_zones+1

    ; camera clamp limits: (map_w * 16) - 256 and (map_h * 16) - 240
    lda #0
    sta cam_max_x+1
    lda map_w
    asl a
    rol cam_max_x+1
    asl a
    rol cam_max_x+1
    asl a
    rol cam_max_x+1
    asl a
    rol cam_max_x+1
    sec
    sbc #<256
    sta cam_max_x
    lda cam_max_x+1
    sbc #>256
    sta cam_max_x+1

    lda #0
    sta cam_max_y+1
    lda map_h
    asl a
    rol cam_max_y+1
    asl a
    rol cam_max_y+1
    asl a
    rol cam_max_y+1
    asl a
    rol cam_max_y+1
    sec
    sbc #<240
    sta cam_max_y
    lda cam_max_y+1
    sbc #>240
    sta cam_max_y+1

    lda #$FF
    sta mrow_id0

    pla                         ; tileset id
    jsr LoadTileset
    lda map_bank                ; LoadTileset switched banks
    jsr SetPrgData
    jsr LoadObjects
    rts
.endproc

; A = tileset id. Copies its metatile tables to work RAM, sets its CHR banks
; and builds the 32-byte palette.
.proc LoadTileset
    tax
    lda tset_bank_tab,x
    jsr SetPrgData
    txa
    asl a
    tay
    lda tset_addr_tab,y
    sta srcp
    lda tset_addr_tab+1,y
    sta srcp+1

    ldy #0
    lda (srcp),y                ; CHR bank for BG tiles $80-$BF
    sta cur_chr4
    ldx #SEL_CHR4
    jsr SetChrBank
    ldy #1
    lda (srcp),y
    sta cur_chr5
    ldx #SEL_CHR5
    jsr SetChrBank

    ; palette: 16 BG bytes from the tileset, 16 sprite bytes from the engine
    ldy #3
    ldx #0
@pal:
    lda (srcp),y
    sta pal_buf,x
    iny
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

    ; metatile tables: 768 bytes at offset 19 -> tset_tl ($6910)
    lda srcp
    clc
    adc #19
    sta srcp
    lda srcp+1
    adc #0
    sta srcp+1
    lda #<tset_tl
    sta dstp
    lda #>tset_tl
    sta dstp+1
    ldx #3                      ; three 256-byte pages
@page:
    ldy #0
@byte:
    lda (srcp),y
    sta (dstp),y
    iny
    bne @byte
    inc srcp+1
    inc dstp+1
    dex
    bne @page
    rts
.endproc

; Copy the map's object list into the entity arrays (index 1 upward; 0 = hero).
.proc LoadObjects
    lda #1
    sta ent_count
    lda map_objn
    beq @done
    lda map_objs
    sta srcp
    lda map_objs+1
    sta srcp+1
    ldx #1                      ; entity slot
    lda #0
    sta obj_i
@lp:
    ldy #0
    lda (srcp),y                ; kind
    sta ent_kind,x
    iny
    lda (srcp),y
    sta ent_gx,x
    iny
    lda (srcp),y
    sta ent_gy,x
    iny
    lda (srcp),y                ; a0
    sta ent_tile,x
    iny
    lda (srcp),y                ; a1
    sta ent_dir,x
    iny
    lda (srcp),y                ; a2
    sta ent_arg,x
    iny
    lda (srcp),y                ; a3
    sta ent_home,x
    iny
    lda (srcp),y                ; a4
    sta ent_a4,x
    ; advance
    lda srcp
    clc
    adc #8
    sta srcp
    lda srcp+1
    adc #0
    sta srcp+1
    inx
    cpx #MAX_ENT
    bcs @fin
    inc obj_i
    lda obj_i
    cmp map_objn
    bcc @lp
@fin:
    stx ent_count
@done:
    rts
.endproc

; =============================================================================
; Map data access
; =============================================================================
.proc SetMapBank
    lda map_bank
    jmp SetPrgData
.endproc

; A = metatile row -> ptr = address of that row's RLE stream.
.proc RowAddr
    asl a
    tay
    lda (map_rowtab),y
    sta ptr
    iny
    lda (map_rowtab),y
    sta ptr+1
    rts
.endproc

; A = metatile row -> mrow_buf0 holds the whole decompressed row.
.proc DecodeRow
    cmp mrow_id0
    beq @done
    sta mrow_id0
    jsr SetMapBank
    lda mrow_id0
    jsr RowAddr
    ldx #0
    ldy #0
@lp:
    lda (ptr),y
    bmi @run                    ; test before INY: INY would clobber N
    iny
    sta mrow_buf0,x
    inx
    cpx map_w
    bcc @lp
    rts
@run:
    iny
    and #$7F
    clc
    adc #2
    sta tmpa
    lda (ptr),y
    iny
    sta tmpb
@rl:
    lda tmpb
    sta mrow_buf0,x
    inx
    dec tmpa
    bne @rl
    cpx map_w
    bcc @lp
@done:
    rts
.endproc

; tmpc = metatile column, A = metatile row -> A = metatile id.
; Partial decode; does not disturb mrow_buf0.
.proc CellAt
    pha                         ; SetMapBank clobbers A (the row number)
    jsr SetMapBank
    pla
    jsr RowAddr
    ldx #0
    ldy #0
@lp:
    lda (ptr),y
    bmi @run                    ; test before INY: INY would clobber N
    iny
    cpx tmpc
    beq @done
    inx
    jmp @lp
@run:
    iny
    and #$7F
    clc
    adc #2
    sta tmpa
    lda (ptr),y
    iny
    sta tmpb
    txa
    clc
    adc tmpa
    tax
    cpx tmpc
    beq @lp                     ; run ended exactly before the target
    bcc @lp
    lda tmpb
@done:
    rts
.endproc

; tgt_gx/tgt_gy -> prop_res = the metatile's property bits.
.proc CellProp
    lda tgt_gx
    sta tmpc
    lda tgt_gy
    jsr CellAt
    tax
    lda tset_prop,x
    sta prop_res
    rts
.endproc

; =============================================================================
; Camera
; =============================================================================
; cam = hero pixel position - (HERO_SX, HERO_SY), clamped to the map.
.proc UpdateCamera
    lda ent_px
    sec
    sbc #HERO_SX
    sta cam_x
    lda ent_pxh
    sbc #0
    sta cam_x+1
    bpl @cxok
    lda #0                      ; negative -> clamp low
    sta cam_x
    sta cam_x+1
    jmp @cy
@cxok:
    lda cam_x+1
    cmp cam_max_x+1
    bcc @cy
    bne @cxhi
    lda cam_x
    cmp cam_max_x
    bcc @cy
@cxhi:
    lda cam_max_x
    sta cam_x
    lda cam_max_x+1
    sta cam_x+1
@cy:
    lda ent_py
    sec
    sbc #HERO_SY
    sta cam_y
    lda ent_pyh
    sbc #0
    sta cam_y+1
    bpl @cyok
    lda #0
    sta cam_y
    sta cam_y+1
    jmp @fin
@cyok:
    lda cam_y+1
    cmp cam_max_y+1
    bcc @fin
    bne @cyhi
    lda cam_y
    cmp cam_max_y
    bcc @fin
@cyhi:
    lda cam_max_y
    sta cam_y
    lda cam_max_y+1
    sta cam_y+1
@fin:
    ; tile coordinates and the PPU scroll for this frame
    lda cam_x+1
    lsr a
    lda cam_x
    ror a
    lsr a
    lsr a
    sta tmpa
    lda cam_x+1
    asl a
    asl a
    asl a
    asl a
    asl a
    ora tmpa
    sta cam_tx                  ; (cam_x >> 3), 8 bits is enough

    lda cam_y+1
    lsr a
    lda cam_y
    ror a
    lsr a
    lsr a
    sta tmpa
    lda cam_y+1
    asl a
    asl a
    asl a
    asl a
    asl a
    ora tmpa
    sta cam_ty

    lda cam_x
    sta scroll_x
    lda ppu_ctrl
    and #%11111110
    sta ppu_ctrl
    lda cam_x+1
    and #1
    ora ppu_ctrl
    sta ppu_ctrl

    ; vertical scroll is cam_y mod 240
    lda cam_y+1
    sta div_n+1
    lda cam_y
    sta div_n
    lda #240
    sta div_d
    jsr Div16
    lda div_r
    sta scroll_y
    rts
.endproc

.import Div16

; =============================================================================
; Drawing the whole map (rendering off)
; =============================================================================
.proc DrawFullMap
    jsr ScreenOff
    lda #0
    sta loop_i
@row:
    lda cam_ty
    clc
    adc loop_i
    jsr BuildRowStrip           ; also leaves the row decoded in mrow_buf0
    lda cam_ty
    clc
    adc loop_i
    jsr RowSlot                 ; A = nametable slot
    sta nt_slot
    jsr WriteStripDirect
    ; attributes once per metatile row (on its top tile row)
    lda cam_ty
    clc
    adc loop_i
    and #1
    bne @next
    lda cam_ty
    clc
    adc loop_i
    lsr a
    jsr AttrRowShadow
@next:
    inc loop_i
    lda loop_i
    cmp #30
    bcc @row

    jsr WriteAttrDirect
    jsr LoadPaletteBuf
    lda cam_tx
    sta prev_cam_tx
    lda cam_ty
    sta prev_cam_ty
    jsr ScreenOn
    rts
.endproc

.proc LoadPaletteBuf
    lda #<pal_buf
    sta ptr
    lda #>pal_buf
    sta ptr+1
    jmp LoadPalette
.endproc

; A = world tile row -> A = row mod 30
.proc RowSlot
    cmp #30
    bcc @done
    sta div_n
    lda #30
    sta div_d
    jsr Div8
    lda div_r
@done:
    rts
.endproc

; Write stripbuf to both nametables at nt_slot, with rendering off.
.proc WriteStripDirect
    lda nt_slot
    lsr a
    lsr a
    lsr a
    clc
    adc #$20
    sta tmpa
    lda nt_slot
    and #7
    asl a
    asl a
    asl a
    asl a
    asl a
    tax
    lda tmpa
    jsr PpuAddr
    ldy #0
@l0:
    lda stripbuf,y
    sta PPUDATA
    iny
    cpy #32
    bne @l0
    lda tmpa
    clc
    adc #4                      ; $2400 nametable
    sta tmpa
    lda nt_slot
    and #7
    asl a
    asl a
    asl a
    asl a
    asl a
    tax
    lda tmpa
    jsr PpuAddr
    ldy #32
@l1:
    lda stripbuf,y
    sta PPUDATA
    iny
    cpy #64
    bne @l1
    rts
.endproc

; Push both attribute shadows to VRAM, with rendering off.
.proc WriteAttrDirect
    lda #$23
    ldx #$C0
    jsr PpuAddr
    ldy #0
@l0:
    lda attr_shadow,y
    sta PPUDATA
    iny
    cpy #64
    bne @l0
    lda #$27
    ldx #$C0
    jsr PpuAddr
    ldy #0
@l1:
    lda attr_shadow_r,y
    sta PPUDATA
    iny
    cpy #64
    bne @l1
    rts
.endproc

; =============================================================================
; Building a tile row strip
; =============================================================================
; A = world tile row. Fills stripbuf[0..63], indexed by nametable column.
.proc BuildRowStrip
    sta tmpd
    lsr a
    jsr DecodeRow
    lda tmpd
    and #1
    beq @top
    lda #<tset_bl
    sta srcp
    lda #>tset_bl
    sta srcp+1
    lda #<tset_br
    sta ptr2
    lda #>tset_br
    sta ptr2+1
    jmp @go
@top:
    lda #<tset_tl
    sta srcp
    lda #>tset_tl
    sta srcp+1
    lda #<tset_tr
    sta ptr2
    lda #>tset_tr
    sta ptr2+1
@go:
    lda cam_tx
    and #63
    sta strip_i
    lda cam_tx
    sta wx
    lda #0
    sta wx+1
    ldx #64
@lp:
    lda wx+1
    lsr a
    lda wx
    ror a
    cmp map_w
    bcc :+
    lda map_w
    sec
    sbc #1
:   tay
    lda mrow_buf0,y
    tay
    lda wx
    and #1
    bne @right
    lda (srcp),y
    jmp @put
@right:
    lda (ptr2),y
@put:
    ldy strip_i
    sta stripbuf,y
    iny
    tya
    and #63
    sta strip_i
    inc wx
    bne :+
    inc wx+1
:   dex
    bne @lp
    rts
.endproc

; =============================================================================
; Attributes
; =============================================================================
; A = metatile row, tmp6 = palette to force ($FF = take it from the map).
.proc AttrRowForce
    jmp AttrRowCore
.endproc

; A = metatile row. Folds that row's palettes into the attribute shadows.
.proc AttrRowShadow
    ldy #$FF
    sty tmp6
    ; fall through
.endproc

.proc AttrRowCore
    sta tmpd                    ; MY
    jsr DecodeRow               ; cached; needed for the map's palettes
    lda tmpd
    asl a                       ; WY = MY*2
    jsr RowSlot
    sta tmpa                    ; r = WY mod 30
    lsr a
    lsr a
    sta atr_row                 ; r >> 2
    lda tmpa
    lsr a
    and #1
    sta atr_qy                  ; 0 or 1

    ; iterate the 32 metatile columns of the window
    lda cam_tx
    lsr a
    sta mt_col                  ; first metatile column (cam_tx/2)
    lda #0
    sta loop_j
@lp:
    lda tmp6
    bpl @forced
    lda mt_col
    cmp map_w
    bcs @skip
    tay
    lda mrow_buf0,y
    tay
    lda tset_attr,y
    jmp @havepal
@forced:
    lda tmp6
@havepal:
    sta tmpb                    ; palette 0..3
    ; nametable tile column of this metatile
    lda mt_col
    asl a                       ; c = MX*2 (mod 64 via and)
    and #63
    sta tmpc
    lsr a
    lsr a                       ; ntc>>2 for the low 32 columns...
    and #7
    sta tmpa                    ; attribute column 0..7
    lda tmpc
    lsr a
    and #1
    sta tmp0                    ; qx
    ; shadow index = atr_row*8 + attr_col
    lda atr_row
    asl a
    asl a
    asl a
    clc
    adc tmpa
    tax
    ; bit position = qy*4 + qx*2
    lda atr_qy
    asl a
    asl a
    clc
    adc tmp0
    adc tmp0
    sta tmp1                    ; shift
    lda #3
    ldy tmp1
    beq @noshift
@sh:
    asl a
    dey
    bne @sh
@noshift:
    eor #$FF
    sta tmp2                    ; mask of bits to clear
    lda tmpb
    ldy tmp1
    beq @noshift2
@sh2:
    asl a
    dey
    bne @sh2
@noshift2:
    sta tmp3                    ; palette bits in place
    ; which nametable?
    lda tmpc
    cmp #32
    bcs @right
    lda attr_shadow,x
    and tmp2
    ora tmp3
    sta attr_shadow,x
    jmp @skip
@right:
    lda attr_shadow_r,x
    and tmp2
    ora tmp3
    sta attr_shadow_r,x
@skip:
    inc mt_col
    inc loop_j
    lda loop_j
    cmp #32
    bcs :+
    jmp @lp
:   rts
.endproc

; =============================================================================
; Streaming
; =============================================================================
.proc StreamCheck
    lda cam_ty
    cmp prev_cam_ty
    beq @cols
    bcc @up
    ; moved down: the incoming row is the new bottom
    lda cam_ty
    clc
    adc #29
    jsr StreamRow
    jmp @doney
@up:
    lda cam_ty
    jsr StreamRow
@doney:
    lda cam_ty
    sta prev_cam_ty
    rts                         ; at most one axis per frame
@cols:
    lda cam_tx
    cmp prev_cam_tx
    beq @none
    bcc @left
    lda cam_tx
    clc
    adc #31
    jsr StreamCol
    jmp @donex
@left:
    lda cam_tx
    jsr StreamCol
@donex:
    lda cam_tx
    sta prev_cam_tx
@none:
    rts
.endproc

; A = world tile row to stream in.
.proc StreamRow
    sta tmpd
    jsr BuildRowStrip
    lda tmpd
    jsr RowSlot
    sta nt_slot

    ; NT0 half
    lda nt_slot
    lsr a
    lsr a
    lsr a
    clc
    adc #$20
    sta vb_hi
    lda nt_slot
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
@c0:
    lda stripbuf,y
    sta (vb_dat),y
    iny
    cpy #32
    bne @c0

    ; NT1 half
    lda vb_hi
    clc
    adc #4
    sta vb_hi
    lda #1
    sta vb_mode
    lda #32
    sta vb_cnt
    jsr VBufAlloc
    bcs @done
    ldy #0
@c1:
    lda stripbuf+32,y
    sta (vb_dat),y
    iny
    cpy #32
    bne @c1

    ; attributes, once per metatile row
    lda tmpd
    and #1
    bne @done
    lda tmpd
    lsr a
    jsr AttrRowShadow
    jsr QueueAttrRow
@done:
    rts
.endproc

; Queue the 8+8 attribute bytes of atr_row to both nametables.
.proc QueueAttrRow
    lda atr_row
    asl a
    asl a
    asl a
    sta tmpa                    ; shadow offset
    clc
    adc #$C0
    sta vb_lo
    lda #$23
    sta vb_hi
    lda #1
    sta vb_mode
    lda #8
    sta vb_cnt
    jsr VBufAlloc
    bcs @done
    ldy #0
    ldx tmpa
@c0:
    lda attr_shadow,x
    sta (vb_dat),y
    inx
    iny
    cpy #8
    bne @c0

    lda tmpa
    clc
    adc #$C0
    sta vb_lo
    lda #$27
    sta vb_hi
    lda #1
    sta vb_mode
    lda #8
    sta vb_cnt
    jsr VBufAlloc
    bcs @done
    ldy #0
    ldx tmpa
@c1:
    lda attr_shadow_r,x
    sta (vb_dat),y
    inx
    iny
    cpy #8
    bne @c1
@done:
    rts
.endproc

; A = world tile column to stream in.
.proc StreamCol
    sta strm_idx                ; WX (0..255)
    lsr a
    sta mt_col                  ; MX
    cmp map_w
    bcc :+
    rts                         ; off the map: nothing to draw
:
    ; choose the metatile half
    lda strm_idx
    and #1
    beq @left
    lda #<tset_tr
    sta srcp
    lda #>tset_tr
    sta srcp+1
    lda #<tset_br
    sta ptr2
    lda #>tset_br
    sta ptr2+1
    jmp @go
@left:
    lda #<tset_tl
    sta srcp
    lda #>tset_tl
    sta srcp+1
    lda #<tset_bl
    sta ptr2
    lda #>tset_bl
    sta ptr2+1
@go:
    ; fill colbuf[slot] for the 30 visible rows
    lda #0
    sta loop_i
@lp:
    lda cam_ty
    clc
    adc loop_i
    sta tmpd                    ; WY
    lsr a                       ; MY
    sta tmpa
    cmp map_h
    bcc :+
    lda map_h
    sec
    sbc #1
    sta tmpa
:   lda mt_col
    sta tmpc
    lda tmpa
    jsr CellAt
    tay
    lda cam_ty
    clc
    adc loop_i
    and #1
    bne @bot
    lda (srcp),y
    jmp @put
@bot:
    lda (ptr2),y
@put:
    sta tmpb
    lda cam_ty
    clc
    adc loop_i
    jsr RowSlot
    tax
    lda tmpb
    sta colbuf,x
    inc loop_i
    lda loop_i
    cmp #30
    bcc @lp

    ; queue the column write (PPU address increments by 32)
    lda strm_idx
    and #63
    sta tmpc                    ; nametable tile column 0..63
    cmp #32
    bcc @nt0
    lda #$24
    sta vb_hi
    lda tmpc
    and #31
    sta vb_lo
    jmp @alloc
@nt0:
    lda #$20
    sta vb_hi
    lda tmpc
    sta vb_lo
@alloc:
    lda #2
    sta vb_mode
    lda #30
    sta vb_cnt
    jsr VBufAlloc
    bcs @done
    ldy #0
@cp:
    lda colbuf,y
    sta (vb_dat),y
    iny
    cpy #30
    bne @cp
    jsr AttrColUpdate
@done:
    rts
.endproc

; Update and queue the 8 attribute bytes of one metatile column.
.proc AttrColUpdate
    lda strm_idx
    and #63
    sta tmpc                    ; nametable tile column
    lsr a
    lsr a
    and #7
    sta atr_col                 ; attribute column 0..7 (NOT tmpa: the CellAt
                                ; in the loop below uses tmpa as scratch)
    lda tmpc
    lsr a
    and #1
    sta tmp0                    ; qx

    lda #0
    sta loop_i
@lp:
    ; metatile row for this slice entry
    lda cam_ty
    lsr a
    clc
    adc loop_i
    sta tmpd                    ; MY
    cmp map_h
    bcs @next
    lda mt_col
    sta tmpc
    lda tmpd
    jsr CellAt
    tay
    lda tset_attr,y
    sta tmpb
    lda tmpd
    asl a
    jsr RowSlot
    sta tmp4                    ; r
    lsr a
    lsr a
    sta atr_row
    lda tmp4
    lsr a
    and #1
    sta atr_qy
    ; shadow index
    lda atr_row
    asl a
    asl a
    asl a
    clc
    adc atr_col
    tax
    lda atr_qy
    asl a
    asl a
    clc
    adc tmp0
    adc tmp0
    sta tmp1
    lda #3
    ldy tmp1
    beq @ns
@sh:
    asl a
    dey
    bne @sh
@ns:
    eor #$FF
    sta tmp2
    lda tmpb
    ldy tmp1
    beq @ns2
@sh2:
    asl a
    dey
    bne @sh2
@ns2:
    sta tmp3
    lda strm_idx
    and #63
    cmp #32
    bcs @right
    lda attr_shadow,x
    and tmp2
    ora tmp3
    sta attr_shadow,x
    jmp @next
@right:
    lda attr_shadow_r,x
    and tmp2
    ora tmp3
    sta attr_shadow_r,x
@next:
    inc loop_i
    lda loop_i
    cmp #16
    bcs :+
    jmp @lp
:
    ; queue the 8 affected bytes (one per attribute row)
    lda #0
    sta loop_i
@q:
    lda loop_i
    asl a
    asl a
    asl a
    clc
    adc atr_col
    sta tmp4                    ; shadow index
    clc
    adc #$C0
    sta vb_lo
    lda strm_idx
    and #63
    cmp #32
    bcs @qr
    lda #$23
    sta vb_hi
    ldx tmp4
    lda attr_shadow,x
    jmp @qgo
@qr:
    lda #$27
    sta vb_hi
    ldx tmp4
    lda attr_shadow_r,x
@qgo:
    sta tmp5
    lda #1
    sta vb_mode
    sta vb_cnt
    jsr VBufAlloc
    bcs @qdone
    ldy #0
    lda tmp5
    sta (vb_dat),y
@qdone:
    inc loop_i
    lda loop_i
    cmp #8
    bcc @q
    rts
.endproc

; =============================================================================
; Hero movement
; =============================================================================
.proc SyncHeroPixels
    lda ent_gx
    asl a
    sta ent_px
    lda #0
    rol a
    sta ent_pxh
    lda ent_px
    asl a
    sta ent_px
    rol ent_pxh
    lda ent_px
    asl a
    sta ent_px
    rol ent_pxh
    lda ent_px
    asl a
    sta ent_px
    rol ent_pxh

    lda ent_gy
    asl a
    sta ent_py
    lda #0
    rol a
    sta ent_pyh
    lda ent_py
    asl a
    sta ent_py
    rol ent_pyh
    lda ent_py
    asl a
    sta ent_py
    rol ent_pyh
    lda ent_py
    asl a
    sta ent_py
    rol ent_pyh
    rts
.endproc

.proc UpdateHero
    lda ent_state
    bne @moving
    ; idle: take a direction from the pad
    lda pad1
    and #BTN_UP
    beq :+
    lda #DIR_UP
    jmp @try
:   lda pad1
    and #BTN_DOWN
    beq :+
    lda #DIR_DOWN
    jmp @try
:   lda pad1
    and #BTN_LEFT
    beq :+
    lda #DIR_LEFT
    jmp @try
:   lda pad1
    and #BTN_RIGHT
    beq @none
    lda #DIR_RIGHT
@try:
    sta ent_dir
    jsr TryStep
@none:
    rts
@moving:
    ; slide MOVE_SPEED pixels in the facing direction
    lda ent_dir
    cmp #DIR_UP
    bne :+
    lda ent_py
    sec
    sbc #MOVE_SPEED
    sta ent_py
    lda ent_pyh
    sbc #0
    sta ent_pyh
    jmp @tick
:   cmp #DIR_DOWN
    bne :+
    lda ent_py
    clc
    adc #MOVE_SPEED
    sta ent_py
    lda ent_pyh
    adc #0
    sta ent_pyh
    jmp @tick
:   cmp #DIR_LEFT
    bne :+
    lda ent_px
    sec
    sbc #MOVE_SPEED
    sta ent_px
    lda ent_pxh
    sbc #0
    sta ent_pxh
    jmp @tick
:   lda ent_px
    clc
    adc #MOVE_SPEED
    sta ent_px
    lda ent_pxh
    adc #0
    sta ent_pxh
@tick:
    lda ent_timer
    sec
    sbc #MOVE_SPEED
    sta ent_timer
    bne @out
    lda #ST_IDLE
    sta ent_state
    lda tgt_gx
    sta ent_gx
    lda tgt_gy
    sta ent_gy
    jsr CheckWarp
    lda gamestate
    cmp #GS_FIELD
    bne @out
    jsr CheckTrigger
    lda gamestate
    cmp #GS_FIELD
    bne @out
    jsr CheckEncounter
@out:
    rts
.endproc

; One step taken: maybe start a battle.
.proc CheckEncounter
.ifdef TEST_NO_ENCOUNTERS
    rts                         ; test builds walk without interruption
.endif
    lda enc_rate
    beq @none
    lda tgt_gx
    sta tmpc
    lda tgt_gy
    jsr CellAt
    tax
    lda tset_prop,x
    and #$08                    ; PROP_ENCTR
    beq @none
    inc step_ctr
    lda step_ctr
    cmp #4                      ; never two fights back to back
    bcc @none
    jsr Random
    cmp enc_rate
    bcs @none
    lda #0
    sta step_ctr
    lda #BATTLE_BANK
    jsr SetPrgCode
    jsr RollEncounter
    bcc @none
    pha
    lda #GS_BATTLE
    sta gamestate
    pla
    jsr BattleEnter
@none:
    rts
.endproc

; --- GS_BATTLE ---------------------------------------------------------------
.proc StBattle
    jsr HideSprites
    lda #BATTLE_BANK
    jsr SetPrgCode
    jsr BattleTick
    lda btl_phase
    cmp #10                     ; BP_DONE
    bcc @done
    lda btl_result
    cmp #2                      ; party wiped
    beq @over
    cmp #3                      ; victory: an armed boss is now beaten
    bne @ret
    lda pend_flag
    cmp #$FF
    beq :+
    jsr MarkStory
    lda #$FF
    sta pend_flag
:   lda btl_form
    cmp #FORM_THE_ARCHON        ; the Archon has a second form
    bne :+
    lda #FORM_ARCHON_PRIME
    jsr BattleEnter             ; straight into it, no return to the field
    rts
:   cmp #FORM_ARCHON_PRIME
    bne @ret
    jsr ReturnToField
    jmp StartEnding
@ret:
    jsr ReturnToField
    lda #GS_FIELD
    sta gamestate
    rts
@over:
    lda #GS_GAMEOVER
    sta gamestate
@done:
    rts
.endproc

.proc ReturnToField
    lda map_id
    jsr LoadMap
    jsr UpdateCamera
    jsr DrawFullMap
    rts
.endproc

.proc HideSprites
    ldy #0
    lda #$FF
:   sta OAM_BUF,y
    iny
    bne :-
    rts
.endproc

.proc StGameOver
    lda pad1_new
    and #BTN_A|BTN_START
    beq @done
    ; revive at the last town with half the credits, FF/DQ style
    lda #BATTLE_BANK
    jsr SetPrgCode
    jsr InitParty
    lda #0
    jsr LoadMap
    lda #44
    sta ent_gx
    lda #68
    sta ent_gy
    lda #ST_IDLE
    sta ent_state
    jsr SyncHeroPixels
    jsr UpdateCamera
    jsr DrawFullMap
    lda #GS_FIELD
    sta gamestate
@done:
    rts
.endproc

; Try to step one cell in ent_dir.
.proc TryStep
    lda ent_gx
    sta tgt_gx
    lda ent_gy
    sta tgt_gy
    lda ent_dir
    cmp #DIR_UP
    bne :+
    dec tgt_gy
    bmi @blocked
    jmp @check
:   cmp #DIR_DOWN
    bne :+
    inc tgt_gy
    lda tgt_gy
    cmp map_h
    bcs @blocked
    jmp @check
:   cmp #DIR_LEFT
    bne :+
    dec tgt_gx
    bmi @blocked
    jmp @check
:   inc tgt_gx
    lda tgt_gx
    cmp map_w
    bcs @blocked
@check:
    lda tgt_gy
    bmi @blocked
    lda tgt_gx
    bmi @blocked
    jsr CellProp
    lda prop_res
    and #1                      ; PROP_SOLID
    bne @blocked
    lda #ST_MOVE
    sta ent_state
    lda #16
    sta ent_timer
    rts
@blocked:
    lda ent_gx
    sta tgt_gx
    lda ent_gy
    sta tgt_gy
    rts
.endproc

; =============================================================================
; Sprites
; =============================================================================
HERO_TILE_DOWN = 0
HERO_TILE_UP   = 8
HERO_TILE_SIDE = 16

.proc BuildOAM
    lda #0
    sta oam_ptr
    ; screen position = world pixel - camera
    lda ent_px
    sec
    sbc cam_x
    sta sp_x
    lda ent_py
    sec
    sbc cam_y
    sta sp_y

    ldx ent_dir
    lda dir_tile,x
    sta sp_tile
    lda dir_attr,x
    sta sp_attr

    ldx #0
@lp:
    ldy oam_ptr
    lda sp_y
    clc
    adc slot_dy,x
    sec
    sbc #1
    sta OAM_BUF,y
    iny
    lda sp_attr
    and #$40
    beq :+
    lda sp_tile
    clc
    adc flip_tile,x
    jmp @t
:   lda sp_tile
    clc
    adc slot_tile,x
@t: sta OAM_BUF,y
    iny
    lda sp_attr
    sta OAM_BUF,y
    iny
    lda sp_x
    clc
    adc slot_dx,x
    sta OAM_BUF,y
    iny
    sty oam_ptr
    inx
    cpx #4
    bne @lp

    ; hide the remaining sprites
    ldy oam_ptr
    lda #$FF
@hide:
    sta OAM_BUF,y
    iny
    bne @hide
    rts
.endproc

.segment "ENGRO"
bit_tab:   .byte 1, 2, 4, 8, 16, 32, 64, 128
s_credits: .byte "CREDITS", STR_END

state_tab:
    .addr StField-1
    .addr StBoxOpen-1
    .addr StText-1
    .addr StTextWait-1
    .addr StDialog-1
    .addr StBoxClose-1
    .addr StBattle-1
    .addr StGameOver-1
    .addr StEnded-1

dir_tile:  .byte HERO_TILE_UP, HERO_TILE_DOWN, HERO_TILE_SIDE, HERO_TILE_SIDE
dir_attr:  .byte 0, 0, $40, 0
slot_dx:   .byte 0, 8, 0, 8
slot_dy:   .byte 0, 0, 8, 8
slot_tile: .byte 0, 1, 2, 3
flip_tile: .byte 1, 0, 3, 2
