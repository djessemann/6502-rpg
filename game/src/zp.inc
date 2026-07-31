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
