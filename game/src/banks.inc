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
BANK_TEXT0    = 0
BANK_TEXT1    = 1
BANK_TEXT2    = 2
BANK_MAPS0    = 3
BANK_MAPS1    = 4
BANK_MAPS2    = 5
BANK_MAPS3    = 6
BANK_WORLD    = 7
BANK_TILESETS = 8
BANK_TABLES   = 9
BANK_MUSIC    = 10
BANK_MONSTERS = 11
