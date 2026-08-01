; ram.inc — THE authoritative RAM map (outside zero page).
;
;   $0200-$02FF  shadow OAM (DMA page)
;   $0300-$03FF  VBUF: the NMI transfer queue
;   $0400-$07FF  engine BSS
;   $6000-$67FF  SAVE: the battery-backed save file (this layout IS the format)
;   $6800-$7FFF  WORK: volatile work RAM (also battery-backed, never restored)

OAM_BUF        = $0200

; --- VBUF: a queue of packets, flushed by NMI, terminated by a $00 mode byte.
;     [mode, addr_hi, addr_lo, count, data...]
;       mode 1 = sequential write (PPU address increments by 1)
;       mode 2 = column write     (PPU address increments by 32)
;       mode 3 = fill             (one data byte repeated `count` times)
;       mode 0 = end of queue
VBUF           = $0300
VBUF_END       = $03F8      ; leave a little slack for the terminator
; How many bytes of PPUDATA one NMI may write. Vblank is ~2273 cycles and
; OAM DMA takes 513 of them; the flush loop costs about 16 cycles a byte, so
; 80 bytes is ~1300 cycles and leaves room for the scroll restore. Anything
; still queued slides down and goes out on the next frame.
VBUF_BUDGET    = 80

; --- engine BSS --------------------------------------------------------------
attr_shadow    = $0400      ; 128: two nametables' attribute tables ($0400/$0440)
attr_shadow_r  = $0440
linebuf        = $0480      ; 34: one composed text line
stripbuf       = $04B0      ; 64: one streamed tile row (two 32-tile halves)
colbuf         = $04F0      ; 32: one streamed tile column
colattr        = $0510      ;  8: attribute bytes for a streamed column
msg_buf        = $0520      ; 96: runtime-composed message text
oam_count      = $0580
ent_count      = $0581
map_objn       = $0582      ; number of objects on the current map
enc_rate       = $0583
enc_tab        = $0584      ; current zone encounter table id
sfx_req        = $0585
music_req      = $0586
box_saved      = $0587
misc_bss       = $0588      ; ...spare through $059F
pal_buf        = $05A0      ; 32: assembled palette (16 BG tileset + 16 sprite)
mcol_buf       = $05C0      ; 16: metatile ids of one column slice
digits         = $05D0      ;  6: decimal digit scratch for PutNumber

; Field entities (struct-of-arrays). Index 0 = the party leader.
MAX_ENT        = 16
ent_gx         = $0600
ent_gy         = $0610
ent_px         = $0620      ; world pixel X low
ent_pxh        = $0630      ; world pixel X high
ent_py         = $0640
ent_pyh        = $0650
ent_dir        = $0660
ent_state      = $0670
ent_timer      = $0680
ent_kind       = $0690      ; 0 = none, 1 = npc(bg), 2 = npc(sprite), 3 = chest
ent_arg        = $06A0      ; message id / chest id
ent_tile       = $06B0      ; base BG metatile or sprite tile
ent_home       = $06C0      ; movement anchor / flags
ent_a4         = $06D0      ; the object record's 8th byte (chest credits high)
; $06E0-$07FF spare

; --- SAVE file ($6000-$67FF). Bytes here are the save format. ----------------
SAVE_BASE      = $6000
sav_magic      = $6000      ; 4: "THRN"
sav_sum        = $6004      ; 2: checksum of $6006..$61FF
sav_version    = $6006
sav_pad        = $6007
party          = $6008      ; 4 x 32 bytes
PARTY_SIZE     = 32
inv_id         = $6088      ; 32
inv_ct         = $60A8      ; 32
credits        = $60C8      ; 3 (24-bit)
play_time      = $60CB      ; 3 (frames/60)
cur_map        = $60CE
cur_gx         = $60CF
cur_gy         = $60D0
cur_dir        = $60D1
vehicles       = $60D2      ; bit0 skiff, bit1 grav-lift
party_n        = $60D3
last_town      = $60D4      ; map id for BEACON / game over
ret_map        = $60D5      ; overworld return position when inside a map
ret_gx         = $60D6
ret_gy         = $60D7
save_misc      = $60D8      ; ...spare through $60DF
story_flags    = $60E0      ; 32 bytes = 256 story flags
chest_flags    = $6100      ; 64 bytes = 512 chest flags
SAVE_CKEND     = $6200      ; checksum covers $6006..$61FF

; Character struct offsets (32 bytes each).
c_class        = 0
c_level        = 1
c_xp           = 2          ; 3 bytes
c_hp           = 5          ; 2
c_hpmax        = 7          ; 2
c_tp           = 9
c_tpmax        = 10
c_str          = 11
c_agi          = 12
c_vit          = 13
c_spi          = 14
c_atk          = 15
c_def          = 16
c_eva          = 17
c_hit          = 18
c_status       = 19
c_weapon       = 20
c_armour       = 21
c_shield       = 22
c_helm         = 23
c_psi          = 24         ; 2: bitmask of known PSI techs
c_bio          = 26         ; 2: bitmask of known BIO techs
c_name         = 28
c_sprite       = 29
c_res0         = 30
c_res1         = 31

; Status bits
ST_POISON      = $01
ST_STUN        = $02
ST_BLIND       = $04
ST_SILENCE     = $08
ST_DOWN        = $80

; --- WORK RAM ($6800-$7FFF): volatile. ---------------------------------------
mrow_buf0      = $6800      ; 128: decompressed map metatile row
mrow_buf1      = $6880      ; 128
mrow_id0       = $6900      ; which row is in buf0 ($FF = none)
mrow_id1       = $6901
mrow_next      = $6902      ; which buffer to evict next

tset_tiles     = $6910      ; 4 x 128: metatile -> 4 BG tile ids (TL,TR,BL,BR)
tset_tl        = $6910
tset_tr        = $6990
tset_bl        = $6A10
tset_br        = $6A90
tset_attr      = $6B10      ; 128: metatile -> palette 0..3
tset_prop      = $6B90      ; 128: metatile -> property bits (solid, etc.)

; Battle state (up to 8 combatants: 4 party + 4 enemies)
b_hp           = $6C10      ; 2 x 8
b_hpmax        = $6C20      ; 2 x 8
b_atk          = $6C30      ; 8
b_def          = $6C38
b_agi          = $6C40
b_spi          = $6C48
b_status       = $6C50
b_alive        = $6C58
b_kind         = $6C60      ; monster id for enemies
b_init         = $6C68      ; rolled initiative
b_order        = $6C70      ; turn order (indices)
b_guard        = $6C78
b_evade        = $6C80
b_hit          = $6C88
b_elem         = $6C90      ; enemy element weakness/immunity
b_xp           = $6CA0      ; 2 x 4 accumulators
b_gold         = $6CA8
btl_nenemy     = $6CB0
btl_ntypes     = $6CB1
btl_type0      = $6CB2
btl_type1      = $6CB3
btl_slot_type  = $6CB4      ; 4: which type each enemy slot is
btl_slot_x     = $6CB8      ; 4: screen tile X of each enemy
btl_slot_y     = $6CBC
btl_result     = $6CC0
btl_boss       = $6CC1
btl_round      = $6CC2
btl_scratch    = $6CC3
act_cmd        = $6CC4      ; 4: queued command per party member
act_tgt        = $6CC8      ; 4: its target combatant
act_arg        = $6CCC      ; 4: tech / item id
ord_i          = $6CD0      ; index into the initiative order
n_comb         = $6CD1      ; number of combatants (4 + enemies)
msg_timer      = $6CD2
btl_form       = $6CD3      ; formation id
btl_win        = $6CD4      ; 2: accumulated xp
btl_cred       = $6CD6      ; 2: accumulated credits
mon_rec        = $6CD8      ; 16: the monster record being read
mon_rec2       = $6CE8      ; 16: second type
sel_i          = $6CF8
sel_max        = $6CF9
sel_top        = $6CFA
lvl_i          = $6CFB
tmp_wide       = $6CFC
btl_blink      = $6CFD      ; enemy slot flashed out by a hit ($FF = none)
btl_blinkt     = $6CFE      ; frames until it is painted back
btl_dirty      = $6CFF      ; bitmask of enemy slots whose tiles are out of date
tech_rec       = $6D70      ; 6: the tech record being applied
; What each HUD row is currently showing: hp lo/hi, hpmax lo/hi, tp, status.
; HudTick compares the live stats against this every frame and redraws any row
; that has drifted, so the party's HP is never stale no matter which of the
; two dozen places in this file moved it.
hud_shadow     = $6D76      ; 24: 6 bytes per party member
hud_live       = $6D8E      ; 6: the same six read fresh, for the compare

; Shop / menu scratch
shop_list      = $6D00      ; 16 item ids
shop_n         = $6D10
menu_stack     = $6D11      ; 8
menu_sp        = $6D19
tmp_buf        = $6D20      ; 64 bytes of general scratch
name_buf       = $6D60      ; 8

; Sound driver state
map_ptr_lo     = $6D68      ; current map header pointer (work copy)
map_ptr_hi     = $6D69
snd_state      = $6E00      ; ...through $6EFF


; --- the saved game ($6200-$63FF) --------------------------------------------
; The live game state IS the $6000 block, so a "save" is a copy of it into a
; second slot and a "load" is a copy back. Without the copy every step the
; party took would already be permanent, and dying would overwrite the file.
slot_magic     = $6200      ; 4: "THRN"
slot_sum       = $6204      ; 2: 16-bit sum of the 506 bytes that follow
slot_data      = $6206      ; 506: a copy of $6006..$61FF
SLOT_LEN       = SAVE_CKEND - sav_version    ; 506

; Chosen at the title screen, read by InitParty ($FF = "use the default four").
party_class    = $6F00      ; 4
ti_rowq        = $6F04      ; 24: title-screen row redraw queue (screen row 2+)

; Full-screen menu UI (src/uikit.inc, banks 26 and 29). Fixed addresses, not a
; BSS segment: the linker's BSS would land on top of the map above.
ui_row         = $6F20      ; the screen row the pacer / DrawPage is drawing
ui_cnt         = $6F21
ui_rem         = $6F22      ; Div24By10's remainder
ui_note        = $6F23      ; notice string id under the page (0 = none)
ui_dirty       = $6F24      ; 4: bitmap of screen rows waiting to be redrawn
ui_n24         = $6F28      ; 3: the number PutNumR is formatting
ui_sp          = $6F2B      ; page stack depth
ui_item        = $6F2C      ; the item the menu is about to use / buy / sell
ui_islot       = $6F2D      ; the inventory slot it came from
ui_tech        = $6F2E      ; the tech the menu is about to cast
ui_shop        = $6F2F      ; shop id
ui_rec         = $6F30      ; 8: the item record being read
ui_trec        = $6F38      ; 6: the tech record being read
ui_stkc        = $6F40      ; 6: saved cursor per page-stack level
ui_stkt        = $6F48      ; 6: saved scroll position
ui_list        = $6F50      ; 32: the ids on show
ui_lidx        = $6F70      ; 32: where each came from (inventory slot)

; $6FA0-$7FFF spare
