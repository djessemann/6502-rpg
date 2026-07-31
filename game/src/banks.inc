; banks.inc — PRG bank numbers. One home for the ROM's bank map.
;
;   0..23  DATA banks, mapped at $8000 (MMC3 R6)
;  24..29  CODE banks, mapped at $A000 (MMC3 R7)
;  30      fixed engine bank at $C000
;  31      fixed kernel bank at $E000

; --- code banks ($A000) ---
SOUND_BANK    = 24
BATTLE_BANK   = 25
MENU_BANK     = 26
TITLE_BANK    = 27
BATTLE2_BANK  = 28
SPARE_BANK    = 29

; --- data banks ($8000) ---
; Text banks are contiguous from BANK_TEXT_BASE: message id -> bank
; BANK_TEXT_BASE + (id >> 6), entry (id & 63) in that bank's own address table.
BANK_TEXT_BASE = 0          ; banks 0..3
BANK_MAPS0    = 4
BANK_MAPS1    = 5
BANK_MAPS2    = 6
BANK_MAPS3    = 7
BANK_WORLD    = 8
BANK_TILESETS = 9
BANK_TABLES   = 10
BANK_MUSIC    = 11
BANK_MONSTERS = 12
