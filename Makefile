# Makefile — ca65/ld65 build for the NROM vertical slice.

NAME    := 6502rpg
CFG     := nes.cfg
SRCDIR  := src
SRCS    := $(SRCDIR)/header.s $(SRCDIR)/main.s $(SRCDIR)/field.s $(SRCDIR)/chr.s $(SRCDIR)/messages.s
OBJS    := $(SRCS:.s=.o)

AS      := ca65
LD      := ld65
ASFLAGS := -g -I $(SRCDIR)

.PHONY: all clean

all: $(NAME).nes

$(NAME).nes: $(OBJS) $(CFG)
	$(LD) -C $(CFG) -o $@ $(OBJS) --dbgfile $(NAME).dbg

$(SRCDIR)/%.o: $(SRCDIR)/%.s
	$(AS) $(ASFLAGS) -o $@ $<

clean:
	rm -f $(OBJS) $(NAME).nes $(NAME).dbg
