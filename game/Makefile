# THRENOS — ca65/ld65 build (MMC3, 256KB PRG / 128KB CHR).

NAME    := threnos
CFG     := nes.cfg
SRCDIR  := src
GENDIR  := $(SRCDIR)/gen

SRCS    := $(SRCDIR)/header.s \
           $(SRCDIR)/kernel.s \
           $(SRCDIR)/sound.s \
           $(SRCDIR)/field.s \
           $(GENDIR)/chr.s \
           $(GENDIR)/tables.s \
           $(GENDIR)/tilesets.s \
           $(GENDIR)/maps_world.s \
           $(GENDIR)/maps_area.s

OBJS    := $(SRCS:.s=.o)

AS      := ca65
LD      := ld65
ASFLAGS := -g -I $(SRCDIR)

.PHONY: all clean content

all: $(NAME).nes

content:
	python3 tools/gen_cfg.py
	python3 tools/build.py

$(NAME).nes: $(OBJS) $(CFG)
	$(LD) -C $(CFG) -o $@ $(OBJS) --dbgfile $(NAME).dbg

%.o: %.s
	$(AS) $(ASFLAGS) -o $@ $<

clean:
	rm -f $(OBJS) $(NAME).nes $(NAME).dbg
