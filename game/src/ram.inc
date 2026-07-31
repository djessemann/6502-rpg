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
MAX_ENT        = 12
ent_gx         = $0600
ent_gy         = $060C
ent_px         = $0618      ; world pixel X low
ent_pxh        = $0624      ; world pixel X high
ent_py         = $0630
ent_pyh        = $063C
ent_dir        = $0648
ent_state      = $0654
ent_timer      = $0660
ent_kind       = $066C      ; 0 = none, 1 = npc(bg), 2 = npc(sprite), 3 = chest
ent_arg        = $0678      ; message id / chest id
ent_tile       = $0684      ; base BG metatile or sprite tile
ent_home       = $0690      ; movement anchor / flags
ent_a4         = $069C      ; the object record's 8th byte (chest credits high)
; $06A8-$07FF spare

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
tech_rec       = $6D70      ; 6: the tech record being applied

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

; $6F00-$7FFF spare
