; zp.inc — THE authoritative zero-page map. Hand-allocated, one home per name.
; (Fixed addresses rather than .exportzp so the whole map is visible in one
; place across every bank.)

frame_count   = $00     ; incremented by NMI
ptr           = $01     ; 2 - general pointer
ptr2          = $03     ; 2 - general pointer
srcp          = $05     ; 2 - source pointer (copies)
dstp          = $07     ; 2 - destination pointer (copies)
tmp0          = $09
tmp1          = $0A
tmp2          = $0B
tmp3          = $0C
tmp4          = $0D
tmp5          = $0E
tmp6          = $0F
tmp7          = $10

pad1          = $11     ; buttons held
pad1_prev     = $12
pad1_new      = $13     ; newly pressed this frame

cur_data_bank = $14     ; shadow of MMC3 R6 ($8000 window)
cur_code_bank = $15     ; shadow of MMC3 R7 ($A000 window)
cur_chr4      = $16     ; shadow of MMC3 R4 (BG tiles $80-$BF)
cur_chr5      = $17     ; shadow of MMC3 R5 (BG tiles $C0-$FF)

rng           = $18     ; 2 - LFSR state
rng_tmp       = $1A

; --- NMI <-> main-thread handshake ------------------------------------------
nmi_ready     = $1B     ; nonzero: main thread has queued work for this NMI
ppu_ctrl      = $1C     ; shadow of PPUCTRL written every NMI
ppu_mask      = $1D     ; shadow of PPUMASK
scroll_x      = $1E     ; PPUSCROLL X for this frame
scroll_y      = $1F     ; PPUSCROLL Y for this frame

; --- game state --------------------------------------------------------------
gamestate     = $20
substate      = $21
game_flags    = $22     ; misc engine flags (bit0 = hide party sprite)

; --- camera / field ----------------------------------------------------------
cam_x         = $23     ; 2 - camera world pixel X (0..map_w*16-1)
cam_y         = $25     ; 2 - camera world pixel Y
cam_tx        = $27     ; camera left tile column (cam_x/8) low byte
cam_ty        = $28     ; camera top tile row (cam_y/8) low byte
prev_cam_tx   = $29
prev_cam_ty   = $2A
map_w         = $2B     ; map width in metatiles
map_h         = $2C     ; map height in metatiles
map_id        = $2D
map_bank      = $2E
map_rowtab    = $2F     ; 2 - pointer to the map's row-offset table
map_flags     = $31

; --- streaming ---------------------------------------------------------------
strm_kind     = $32     ; 0 = none, 1 = row, 2 = column
strm_idx      = $33     ; world tile row/column being streamed
strm_nt       = $34     ; destination nametable slot
strm_count    = $35

; --- text / windows ----------------------------------------------------------
msg_ptr       = $36     ; 2
msg_bank      = $38
box_x         = $39     ; box geometry, in screen tiles
box_y         = $3A
box_w         = $3B
box_h         = $3C
box_open      = $3D
cur_line      = $3E
term_action   = $3F
msg_context   = $40
text_delay    = $41
aux_flag      = $42

; --- menus -------------------------------------------------------------------
menu_id       = $43
menu_cursor   = $44
menu_max      = $45
menu_cols     = $46
menu_top      = $47
menu_ret      = $48

; --- entity scratch ----------------------------------------------------------
ent_i         = $49
sp_x          = $4A
sp_y          = $4B
sp_tile       = $4C
sp_attr       = $4D
oam_ptr       = $4E

; --- battle scratch ----------------------------------------------------------
btl_actor     = $4F
btl_target    = $50
btl_phase     = $51
btl_cmd       = $52
dmg_lo        = $53
dmg_hi        = $54
num_lo        = $55     ; number formatting input (16-bit)
num_hi        = $56

; --- generic 16-bit math -----------------------------------------------------
mul_a         = $57
mul_b         = $58
mul_res       = $59     ; 2
div_n         = $5B     ; 2
div_d         = $5D
div_q         = $5E     ; 2
div_r         = $60

; --- audio -------------------------------------------------------------------
snd_bank      = $61
snd_tmp       = $62     ; 2

; --- misc engine -------------------------------------------------------------
step_ctr      = $64     ; steps since the last random encounter
enc_zone      = $65
warp_req      = $66
fade_level    = $67
scratch       = $68     ; 8 bytes of general scratch ($68-$6F)

; $70-$FF are free for subsystem-local use; see the subsystem's source file.
vram_lo       = $70
vram_hi       = $71
vram_cnt      = $72
vram_ptr      = $73     ; 2
row_ptr       = $75     ; 2
col_ptr       = $77     ; 2
mt_ptr        = $79     ; 2
attr_ptr      = $7B     ; 2
copy_len      = $7D
loop_i        = $7E
loop_j        = $7F

; --- VBUF packet builder (main thread) ---------------------------------------
vbuf_wp       = $80     ; 2 - write pointer into VBUF
vb_mode       = $82     ; packet mode for VBufAlloc
vb_hi         = $83     ; PPU address high
vb_lo         = $84     ; PPU address low
vb_cnt        = $85     ; byte count
vb_dat        = $86     ; 2 - VBufAlloc result: pointer to the packet's data

; --- field / streaming scratch ($88-$9F) -------------------------------------
fx0           = $88
fx1           = $89
fx2           = $8A
fx3           = $8B
fx4           = $8C
fx5           = $8D
fx6           = $8E
fx7           = $8F
seg_base      = $90     ; SplitRange: nametable base high byte of segment 1
seg_col       = $91
seg_cnt       = $92
seg2_base     = $93
seg2_cnt      = $94
mt_row        = $95
mt_col        = $96
tile_row      = $97
half          = $98
sub_i         = $99
sub_j         = $9A
row_src       = $9B     ; 2
dir_tmp       = $9D
step_tmp      = $9E
coll_res      = $9F

; --- map / field engine ($A0-$BF) --------------------------------------------
map_objs      = $A0     ; 2 - pointer to the current map's object list
map_zones     = $A2     ; 2 - pointer to its 8x8 encounter-zone grid (0 = none)
map_music     = $A4
nt_slot       = $A5     ; nametable row slot (WY mod 30)
wx            = $A6     ; 2 - world tile column being processed
wy            = $A8     ; 2 - world tile row being processed
strip_i       = $AA
mt_id         = $AB
cam_max_x     = $AC     ; 2 - camera clamp limits for this map
cam_max_y     = $AE     ; 2
dir_req       = $B0
walk_cd       = $B1
obj_i         = $B2
obj_ptr       = $B3     ; 2
tgt_gx        = $B5
tgt_gy        = $B6
prop_res      = $B7
tmpa          = $B8
tmpb          = $B9
tmpc          = $BA
tmpd          = $BB
atr_row       = $BC
atr_qy        = $BD
mcol_mx       = $BE     ; metatile column cached in mcol_buf ($FF = none)
strm_dir      = $BF

; --- window / text job ($C0-$CF) ---------------------------------------------
job_step      = $C0
draw_mode     = $C1     ; 0 = opening the window, 1 = closing it
msg_id        = $C3
talk_ent      = $C4
box_ctx       = $C5
box_done      = $C6
box_row_i     = $C7     ; window job: current screen row (tmpd is not safe:
box_cnt       = $C8     ; BuildRowStrip and AttrRowCore both use tmpd)
list_kind     = $C9     ; which battle list the UI is showing
ui_pending    = $CA     ; bitmask of window interior lines needing a redraw
pend_kind     = $CB     ; a detail line to add under the next message:
pend_lo       = $CC     ;   0 none, 1 = "<n> CREDITS", 2 = an item name
pend_hi       = $CD
pend_item     = $CE
pend_form     = $CF     ; a boss to fight once the message window closes ($FF)
pend_flag     = $D0     ; the story flag that boss's victory sets ($FF none)
msg_chain     = $D1     ; extra consecutive message ids to show after this one
chain_n       = $D2     ; ShowMessageChain's count (tmpa is SetMessage scratch)
atr_col       = $D3     ; AttrColUpdate's attribute column (CellAt eats tmpa)

; --- cross-bank calls (kernel, FarCallRet) -----------------------------------
far_bank      = $E4     ; the bank the target routine lives in
far_ret       = $E5     ; the caller's bank, put back when the target returns

; --- full-screen menu UI (src/uikit.inc; banks 26 and 29) --------------------
; Only the menu/shop banks touch these, and they never run while the field or
; battle does. ui_a..ui_col are scratch for the page composers, which must not
; use tmpa-tmpd or X across PutString / PutNumR / Mul8.
ui_page       = $E6     ; page id within the menu (or the shop)
ui_cur        = $E7     ; cursor: index of the highlighted entry
ui_top        = $E8     ; first visible entry of a scrolling list
ui_max        = $E9     ; number of entries on this page
ui_who        = $EA     ; the party member the page is acting on
ui_slot       = $EB     ; equipment slot (0 weapon, 1 armour, 2 shield, 3 helm)
ui_ptr        = $EC     ; 2 - composer dispatch pointer (ptr belongs to strings)
ui_a          = $EE     ; composer scratch
ui_b          = $EF
ui_c          = $F0
ui_d          = $F1
ui_e          = $F2
ui_col        = $F3     ; PutNumR's write column
ui_mode       = $F4     ; 0 = queue rows through VBUF, 1 = write straight to VRAM
ui_req        = $F5     ; what the menu wants the field to do on the way out:
                        ;   0 nothing, 1 warp to the last town, 2 leave a dungeon
ui_spare      = $F6     ; 2 - unused, reserved for this subsystem
