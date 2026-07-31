# THRENOS -- game script.
#
# Every line of text in the game lives here. Generated data is emitted from
# this table by the build; nothing here is hand-edited downstream.
#
# Format: MESSAGES is a list of (ID, text) tuples.
#   '\n' forces a line break, '\f' forces a page break.
#   Box is 30 characters wide, 4 lines per page, 3 pages maximum.
#   Legal characters: A-Z a-z 0-9 space . , ! ? ' " - : ; / ( ) % + = *
#   (lowercase is folded to uppercase at build time)

MESSAGES = [

    # ------------------------------------------------------------------
    # 1. Opening narration
    # ------------------------------------------------------------------
    ("MSG_INTRO_1",
     "Two hundred years ago the ark\nEREBUS IX fell out of the sky\nover the planet THRENOS."
     "\fIt did not fall by accident.\nSomething in the deep crust\nreached up and took hold\nof it."),

    ("MSG_INTRO_2",
     "Twelve thousand slept aboard.\nEleven hundred walked away\nfrom the wreck."
     "\fThey were engineers. So they\ndid the only thing engineers\ndo. They made the wreck\nwork."),

    ("MSG_INTRO_3",
     "They cut the ark's four drive\ncores out of the hull and\nbuilt a station on each one."
     "\fCINDER. TIDE. STORM. HOLLOW.\nThe four ANCHORS."
     "\fThe cores made power. They\nalso held the weather down,\nheld the ground still, held\nthe machine-life asleep."),

    ("MSG_INTRO_4",
     "Four Anchors. Four regions.\nTwo hundred years of a small,\nstubborn civilisation."
     "\fLong enough that nobody\nalive remembers the sky\nbeing quiet. They only\nremember it being ours."),

    ("MSG_INTRO_5",
     "Then the Anchors began to go\ndark. One after another."
     "\fThe sea came up the terraces.\nThe lightning stopped moving\non. The dunes started\nwalking."
     "\fThe sky is bleeding."),

    ("MSG_INTRO_6",
     "At the bottom of the Rift, in\nthe sealed hull of the ark,\nsomething that calls itself\nTHE ARCHON is finishing"
     "\fa two hundred year\ncalculation."
     "\fIn Landfall, the medical bay\nopens four cold cells it has\nkept in reserve since the\nfall."),

    # ------------------------------------------------------------------
    # Waking / prologue beats
    # ------------------------------------------------------------------
    ("MSG_STORY_WAKE_1",
     "The cell drains. Cold light.\nA voice reads off your vitals\nlike a shopping list."),

    ("MSG_STORY_WAKE_2",
     "MEDTECH SORREL: You are the\nreserve crew. Woken for an\nemergency worth waking you\nfor."
     "\fCongratulations. This is\nthat."),

    ("MSG_STORY_WAKE_3",
     "MEDTECH SORREL: Four of you.\nFour Anchors going dark.\nI would call that tidy if I\nthought it was a coincidence."),

    ("MSG_STORY_WAKE_4",
     "MEDTECH SORREL: Take the\nstairs up to town. Talk to\npeople. Then go east, and\nput the fire back in CINDER."),

    # ------------------------------------------------------------------
    # 2. Towns -- LANDFALL
    # ------------------------------------------------------------------
    ("MSG_LANDFALL_NPC1",
     "You are the sleepers, then.\nTwo centuries of power spent\nkeeping four strangers cold.\nI hope you are worth it."),

    ("MSG_LANDFALL_NPC2",
     "This whole town is the ark's\nnose section. The floor you\nare standing on used to be\na ceiling."),

    ("MSG_LANDFALL_NPC3",
     "CINDER went dark first. Head\neast across the black glass\nto the Ashen Verge. EMBER\nREST is on the road there."
     "\fDo not walk past it. It is\nthe last roof before the\nAnchor."),

    ("MSG_LANDFALL_NPC4",
     "Buy MEDKITS before you leave.\nNot two. Enough. The road\nout of here does not care\nhow new you are."),

    ("MSG_LANDFALL_NPC5",
     "Save at the terminal by the\ndoor. If you die out there\nthe planet keeps whatever\nyou did not write down."),

    ("MSG_LANDFALL_NPC6",
     "My grandmother patched the\nsame coolant line forty\nyears. I have patched it\ntwelve. It is a good line."),

    ("MSG_LANDFALL_NPC7",
     "The sky used to be grey.\nNow it has a seam in it,\nover the Rift, and the seam\nis getting wider."),

    ("MSG_LANDFALL_NPC8",
     "Every crate here is\nsomebody's last one. Open\nany chest you find. Nobody\nelse is coming back for it."),

    ("MSG_LANDFALL_NPC9",
     "There were never five\nAnchors, never three. Four\ncores, four stations. Ask\nwhy the ark had four."),

    ("MSG_LANDFALL_INN",
     "Bunk and a hot ration, 20\ncredits. The mattress is ark\nfoam. It has outlived four\nowners. Rest?"),

    ("MSG_LANDFALL_SHOP",
     "Supplies. Everything on the\nshelf was made twice: once\non Earth, once again here\nwhen the first one broke."),

    ("MSG_LANDFALL_ARMS",
     "Arms and plate. I do not ask\nwhat you are walking into.\nI just sell you the thing\nthat comes back."),

    ("MSG_LANDFALL_SAVE",
     "LANDFALL SAVE TERMINAL\nCore link: STABLE\nWrite party record?"),

    # ------------------------------------------------------------------
    # EMBER REST -- Ashen Verge
    # ------------------------------------------------------------------
    ("MSG_EMBER_NPC1",
     "Welcome to EMBER REST. We\nbuilt it out of ash blocks\nbecause ash is the only\nthing the Verge gives free."),

    ("MSG_EMBER_NPC2",
     "When CINDER was lit the\nglass ran cool enough to\ncross barefoot. Try that now\nand we will bury the boots."),

    ("MSG_EMBER_NPC3",
     "The Anchor is north, past\nthe vent field. Three floors\ndown to the core chamber.\nBring something cold."),

    ("MSG_EMBER_NPC4",
     "My brother went in with a\nrepair crew. He said the heat\nwas not the problem. The\nthing in the core was awake."),

    ("MSG_EMBER_NPC5",
     "A tech that chills works on\nthe vent things. A tech that\nburns just feeds them.\nThat is the whole lesson."),

    ("MSG_EMBER_NPC6",
     "Relight the Anchor and the\ncrew chief owes you a\nPASSKEY. Nothing south of\nhere opens without one."),

    ("MSG_EMBER_NPC7",
     "Two hundred years and we\nstill measure the day by\nwhen the vents breathe out.\nClocks lie. Vents do not."),

    ("MSG_EMBER_NPC8",
     "Ash moths lay in the warm\nglass. Step careful. They\ncome up in clouds and they\nremember faces."),

    ("MSG_EMBER_NPC9",
     "Rest before you go down.\nThe Anchor does not have\na bed. It has a floor, and\nthe floor is hot."),

    ("MSG_EMBER_INN",
     "18 credits. The room is over\nthe vent, so it is warm,\nand it hums. You get used\nto the hum. Rest?"),

    ("MSG_EMBER_SHOP",
     "Kits, antitox, torch cells.\nEverything here is priced\nfor people who are going\nnorth, not people staying."),

    ("MSG_EMBER_ARMS",
     "Ash-forged. Heavier than the\nark stock and it holds an\nedge in heat. Look at the\nblades, not the price."),

    ("MSG_EMBER_SAVE",
     "EMBER REST SAVE TERMINAL\nCore link: CINDER -- FAULT\nWrite party record?"),

    # ------------------------------------------------------------------
    # KELPHOLD -- Drowned Shelf
    # ------------------------------------------------------------------
    ("MSG_KELPHOLD_NPC1",
     "KELPHOLD sits on the third\nterrace. It used to sit on\nthe first. We have moved\nit up twice."),

    ("MSG_KELPHOLD_NPC2",
     "TIDE held the sea down. TIDE\nis dark. Do the arithmetic\nand then look out a window."),

    ("MSG_KELPHOLD_NPC3",
     "The Tide Anchor is under the\nkelp city, west along the\nflooded stair. Three floors.\nThe bottom one is wet."),

    ("MSG_KELPHOLD_NPC4",
     "Bring something that puts\nout fire and something that\ncures poison. The shelf has\nplenty of both problems."),

    ("MSG_KELPHOLD_NPC5",
     "When the Anchor lights, the\ndock crew will hand you the\nSKIFF. Shallow water only.\nDo not test it on the deep."),

    ("MSG_KELPHOLD_NPC6",
     "The kelp is not a plant. It\nwas cargo. Somebody in the\nark's hold meant it to grow,\nand it took that seriously."),

    ("MSG_KELPHOLD_NPC7",
     "There is a thing down there\nthe old dive logs call the\nWARDEN. It was on the crew\nmanifest. As equipment."),

    ("MSG_KELPHOLD_NPC8",
     "Twelve houses under water\nnow. We still call them by\nthe family names. It seems\nrude to stop."),

    ("MSG_KELPHOLD_NPC9",
     "North across the Reach there\nis a tower called RELAY\nNINE. If you ever want to be\nmore than you are, go there."),

    ("MSG_KELPHOLD_INN",
     "24 credits. Top floor, dry,\nfor now. We charge for the\nfloor, not the room. Rest?"),

    ("MSG_KELPHOLD_SHOP",
     "Sealed goods only. If the\nwrapper is soft, do not buy\nit, and do not tell me you\nbought it here."),

    ("MSG_KELPHOLD_ARMS",
     "Salt eats plate in a season.\nMine is lacquered. Costs\nmore. Lasts to the bottom\nof the stair."),

    ("MSG_KELPHOLD_SAVE",
     "KELPHOLD SAVE TERMINAL\nCore link: TIDE -- FAULT\nWrite party record?"),

    # ------------------------------------------------------------------
    # HIGH MESA -- Screaming Reach
    # ------------------------------------------------------------------
    ("MSG_MESA_NPC1",
     "HIGH MESA. Everything here\nis strapped down, including\nthe children. You get used\nto the noise or you leave."),

    ("MSG_MESA_NPC2",
     "The lightning used to pass\nthrough. Since STORM went\ndark it stays. It has\nfavourites."),

    ("MSG_MESA_NPC3",
     "The Storm Anchor is at the\ntop of the far mesa. Three\nfloors up, not down. Watch\nyour footing on the ladders."),

    ("MSG_MESA_NPC4",
     "Anything with a coil in it\nhates water and loves you.\nCarry a cure for STUN or you\nwill watch from the floor."),

    ("MSG_MESA_NPC5",
     "Light the Anchor and the\ntower crew give up the LIFT\nCODE. It powers the GRAV-LIFT,\nso ridges stop mattering."),

    ("MSG_MESA_NPC6",
     "RELAY NINE is two hours\neast on the ridge road.\nComms tower. Nobody has\nanswered it in a century."),

    ("MSG_MESA_NPC7",
     "My father called the strikes\nby name. Said the big one\nover the north mesa had come\nback since he was a boy."),

    ("MSG_MESA_NPC8",
     "The birds up here are not\nbirds. They are the ark's\nweather drones, and they have\nhad two centuries to get odd."),

    ("MSG_MESA_NPC9",
     "Three Anchors down and the\nfourth is in the Hollow\nWaste, under the grey dunes.\nYou will need the lift."),

    ("MSG_MESA_INN",
     "30 credits and we bolt the\nshutters. If it wakes you,\nlie still. It passes. Rest?"),

    ("MSG_MESA_SHOP",
     "Cells, kits, and rope. The\nrope is not for climbing.\nIt is for tying yourself to\nsomething heavy."),

    ("MSG_MESA_ARMS",
     "Grounded plate. The braid in\nthe lining takes the strike\nto your boots instead of\nyour heart. Mostly."),

    ("MSG_MESA_SAVE",
     "HIGH MESA SAVE TERMINAL\nCore link: STORM -- FAULT\nWrite party record?"),

    # ------------------------------------------------------------------
    # DUSTGATE -- Hollow Waste
    # ------------------------------------------------------------------
    ("MSG_DUSTGATE_NPC1",
     "DUSTGATE. We sit on the lid\nof a city nobody built. It\nwas here before the ark.\nThat is the whole town motto."),

    ("MSG_DUSTGATE_NPC2",
     "HOLLOW is the last Anchor\nstill lit, and it flickers.\nWhen it goes, the dunes walk\nover us in a night."),

    ("MSG_DUSTGATE_NPC3",
     "The Anchor is three floors\ndown the shaft, west past the\ndead rigs. Weight goes\nstrange down there. Wait."),

    ("MSG_DUSTGATE_NPC4",
     "The things in the shaft do\nnot bleed and do not talk.\nBring a tech that hits what\nis not really there."),

    ("MSG_DUSTGATE_NPC5",
     "Bring back the fourth spark\nand the shaft crew hand you\nthe RIFT KEY. The last door\nis one you should not open."),

    ("MSG_DUSTGATE_NPC6",
     "The buried city is older\nthan us by a long way, and\nits streets are the same\nfour shapes as the Anchors."),

    ("MSG_DUSTGATE_NPC7",
     "South of the dunes there is\na den the diggers call the\nOSSUARY. Two levels of teeth."
     "\fThe best rifle on this\nplanet is at the bottom\nof it."),

    ("MSG_DUSTGATE_NPC8",
     "My crew dug for forty years\nlooking for the ark's black\nbox. We found the city\ninstead. We stopped digging."),

    ("MSG_DUSTGATE_NPC9",
     "THE LAST PORT is east, on\nthe rim of the Rift. Last\nbeds, last shop, last\nterminal. Then just the hull."),

    ("MSG_DUSTGATE_INN",
     "35 credits. Room is below\ngrade, which is quieter and\nonly a little worse for the\nnerves. Rest?"),

    ("MSG_DUSTGATE_SHOP",
     "Dig stock. Half of it came\nout of the city and I do not\nask what it was for. It\nworks. Buy it."),

    ("MSG_DUSTGATE_ARMS",
     "Weighted gear, for when the\nfloor decides down is a\nsuggestion. Heavy is safe\nout here."),

    ("MSG_DUSTGATE_SAVE",
     "DUSTGATE SAVE TERMINAL\nCore link: HOLLOW -- WEAK\nWrite party record?"),

    # ------------------------------------------------------------------
    # THE LAST PORT -- pre-Rift
    # ------------------------------------------------------------------
    ("MSG_PORT_NPC1",
     "THE LAST PORT. Named by\nsomeone with no sense of\nhumour and a very good eye."),

    ("MSG_PORT_NPC2",
     "The Rift is a hundred paces\nthat way. You can hear the\nhull ticking from the rail\non a still day."),

    ("MSG_PORT_NPC3",
     "Four sparks in your pack and\nthe RIFT KEY in your hand?\nThen the gate is yours.\nNobody else here wants it."),

    ("MSG_PORT_NPC4",
     "Four floors of hull between\nthe gate and the bridge.\nThere is no terminal down\nthere. Write your record here."),

    ("MSG_PORT_NPC5",
     "Stock up. Everything you\ncarry down is everything you\nwill have. Nothing sells you\nanything below the rim."),

    ("MSG_PORT_NPC6",
     "The ARCHON was the ark's\nnavigator. Not a person.\nThe system that chose where\nwe would land."),

    ("MSG_PORT_NPC7",
     "It chose here. It brought us\ndown on purpose. Two\nhundred years and it has\nnever once said why."),

    ("MSG_PORT_NPC8",
     "It talks to you personally.\nEveryone who has stood at the\nrail says the same: it says\nyou, and it means you."),

    ("MSG_PORT_NPC9",
     "If you go down and the\nAnchors stay lit, we will\nhold. That is all any of us\nhave ever been asked to do."),

    ("MSG_PORT_INN",
     "40 credits, and I will not\npretend that is fair. It is\nthe last bed on the map.\nRest?"),

    ("MSG_PORT_SHOP",
     "Buy heavy. There is no shop\nin the hull, no chest worth\nthe walk back, and no\nsecond trip."),

    ("MSG_PORT_ARMS",
     "Best plate I have. It came\noff the ark and it is going\nback in. Seems right."),

    ("MSG_PORT_SAVE",
     "LAST PORT SAVE TERMINAL\nCore link: ALL ANCHORS OK\nWrite party record?"),

    # ------------------------------------------------------------------
    # 3. Story beats -- CINDER
    # ------------------------------------------------------------------
    ("MSG_STORY_CINDER_ARRIVE",
     "CINDER ANCHOR\fThe vent field ends at a\ndoor the size of a house.\nIt is warm to the hand.\nBehind it, nothing runs."),

    ("MSG_STORY_CINDER_DOOR",
     "The blast door reads your\ncold-storage tags, thinks\nabout it for a long moment,\nand opens.\fIt has been waiting for\nreserve crew."),

    ("MSG_STORY_CINDER_CORE",
     "The core chamber. The drive\nring is black and the coolant\nis boiling anyway."
     "\fSomething stands up out of\nthe slag, and the slag comes\nwith it."),

    ("MSG_STORY_CINDER_RELIGHT",
     "You seat the rod. The ring\ncatches, stutters, and holds."
     "\fLight runs out along the\nvent field faster than sound."
     "\fAbove ground, in Ember Rest,\npeople stop working to look\nnorth."),

    ("MSG_STORY_CINDER_SPARK",
     "A hand-sized shard drops out\nof the ring housing, still\nlit.\fCINDER SPARK obtained.\nOne of four. The Anchor kept\nit for whoever came."),

    ("MSG_STORY_CINDER_PASSKEY",
     "CREW CHIEF VASK: You lit it.\nI watched you do it and I\nstill do not believe it.\fTake the PASSKEY. It opens\nthe Sunken Causeway south.\nTIDE is next, and TIDE has\nbeen dark longer."),

    ("MSG_STORY_CAUSEWAY_1",
     "SUNKEN CAUSEWAY\fThe passkey turns in a lock\nthat has been under water\nfor sixty years. The road\ndown is dry."),

    ("MSG_STORY_CAUSEWAY_2",
     "Halfway across, the pumps\nnotice you and start.\fSomething far off in the\ndark notices the pumps."),

    # TIDE
    ("MSG_STORY_TIDE_ARRIVE",
     "TIDE ANCHOR\fThe stair goes down into the\nkelp city. Windows on both\nsides. Lights on in some\nof them."),

    ("MSG_STORY_TIDE_DOOR",
     "The seal cycles. Water goes\nout, air comes in, and the\nair is two hundred years\nold and tastes it."),

    ("MSG_STORY_TIDE_CORE",
     "The core sits in a flooded\nwell. The ring is dark and\nthe water above it is not\nmoving the way water moves."
     "\fThe old dive logs listed it\nas equipment."),

    ("MSG_STORY_TIDE_RELIGHT",
     "The ring lights. The well\ndrains in one long pull.\fOut on the shelf the sea\nsteps back off the second\nterrace and stays there,\nlike it was told."),

    ("MSG_STORY_TIDE_SPARK",
     "TIDE SPARK obtained.\fCold in the hand, and it\nkeeps a small tide of its\nown, in and out, in and\nout."),

    ("MSG_STORY_TIDE_SKIFF",
     "DOCKMASTER ILA: Two down.\nTake the SKIFF. It crosses\nshallow water and nothing\ndeeper."
     "\fSTORM is north, past the\nReach. Good luck with the\nnoise."),

    # STORM
    ("MSG_STORY_STORM_ARRIVE",
     "STORM ANCHOR\fThe tower goes up out of the\nmesa. Every rung is welded\ntwice. The air tastes like\na coin."),

    ("MSG_STORY_STORM_DOOR",
     "The hatch is fused shut by\nold strikes. It takes both\nhands, then it takes four."),

    ("MSG_STORY_STORM_CORE",
     "The ring hangs at the top of\nthe tower, dark, and the\nstorm is standing inside it\nwith its wings out."
     "\fIt has been standing there\nsince the light went off."),

    ("MSG_STORY_STORM_RELIGHT",
     "The ring takes. The strike\nover the north mesa lifts,\ndrifts, and finally moves on\nthe way weather should."
     "\fHigh Mesa is quiet for the\nfirst time in eleven years."),

    ("MSG_STORY_STORM_SPARK",
     "STORM SPARK obtained.\fIt will not sit still in the\npack. It leans, always, in\none direction: down, and\neast, toward the Rift."),

    ("MSG_STORY_STORM_LIFTCODE",
     "TOWER CHIEF REN: Here. The\nLIFT CODE. It wakes every\nGRAV-LIFT plate still\nstanding."
     "\fRidges and chasms stop\nbeing walls."
     "\fAnd go by RELAY NINE. It has\nbeen calling for crew for a\nhundred years. You are crew."),

    # RELAY NINE / promotion
    ("MSG_STORY_RELAY_1",
     "RELAY NINE\fA comms tower with nothing\nleft to talk to. The dish is\nstill turning. The log has\none line in it, repeated."),

    ("MSG_STORY_RELAY_2",
     "LOG: REQUESTING QUALIFIED\nCREW. REQUESTING QUALIFIED\nCREW. REQUESTING QUALIFIED\nCREW.\fThe date on the last entry\nis ninety-eight years ago."),

    ("MSG_STORY_RELAY_3",
     "The dish stops turning and\npoints at you."
     "\fVOICE: Reserve crew. Cold\nstorage tags valid."
     "\fYou have been carrying half\na rating each. That was\nnever the intent."),

    ("MSG_STORY_RELAY_4",
     "VOICE: The ark trained its\ncrew twice. Once to survive\nthe fall, once for what came\nafter.\fNobody stayed alive long\nenough for the second\ncourse. Stand still."),

    ("MSG_STORY_RELAY_5",
     "Light goes through you,\nunhurried, like an inventory\nbeing taken.\fThe party has been promoted\nto veteran ratings."),

    ("MSG_STORY_RELAY_6",
     "VOICE: Records updated. Top\ntech tiers unlocked. Better\ngear will now answer to you.\fI have nothing else. I have\nhad nothing else for ninety\neight years. Go on."),

    # HOLLOW
    ("MSG_STORY_HOLLOW_ARRIVE",
     "HOLLOW ANCHOR\fThe shaft drops through grey\ndune into streets. Not the\nark's streets. Older, and\nsquarer, and empty."),

    ("MSG_STORY_HOLLOW_DOOR",
     "The Anchor was built into a\nwall that was already here.\nThey cut their door next to\none they could not open."),

    ("MSG_STORY_HOLLOW_CORE",
     "The ring is flickering, the\nlast one still trying.\fSomething enormous is\nholding it closed, patiently,\nthe way a hand holds a moth."),

    ("MSG_STORY_HOLLOW_RELIGHT",
     "The ring steadies. Weight\nremembers which way it goes.\fAll four Anchors are lit for\nthe first time in six years,\nand every one of them is\npointing at the Rift."),

    ("MSG_STORY_HOLLOW_SPARK",
     "HOLLOW SPARK obtained.\fFour sparks. Held together\nthey pull toward each other,\nand toward something further\ndown."),

    ("MSG_STORY_HOLLOW_RIFTKEY",
     "SHAFT BOSS OKONKWO: Four for\nfour. Nobody has ever said\nthat sentence before."
     "\fHere is the RIFT KEY. It\nopens the gate on the rim."
     "\fAnd I want it on record that\nI told you not to use it."),

    # OSSUARY
    ("MSG_STORY_OSSUARY_1",
     "THE OSSUARY\fThe diggers named it for what\nis on the floor. Two levels\nof it, sorted by size."),

    ("MSG_STORY_OSSUARY_2",
     "Nothing in here came off the\nark. Whatever eats here has\nbeen eating since before we\nfell."),

    ("MSG_STORY_OSSUARY_3",
     "In a nest of bone and cable,\na rifle, cleaned and racked\nby something with hands.\fIt is the finest weapon on\nthis planet, and it was kept\nlike a trophy."),

    # RIFT
    ("MSG_STORY_RIFT_1",
     "THE RIFT\fThe key turns. The gate on\nthe rim opens on a stair\ncut into the wall of a\nwound."),

    ("MSG_STORY_RIFT_2",
     "Four beams come down out of\nthe sky behind you, one from\neach Anchor, and meet a mile\nbelow.\fThe hull of the EREBUS IX\nis lit for the first time in\ntwo hundred years."),

    ("MSG_STORY_RIFT_3",
     "ARCHON: You opened it. I\nwant you to be clear that\nyou opened it.\fI have not moved in two\nhundred years. Come down."),

    ("MSG_STORY_HULL_1",
     "EREBUS HULL -- DECK ONE\fCorridors the colony has\nnever seen. Dust with no\nfootprints. The lights come\non ahead of you, politely."),

    ("MSG_STORY_HULL_2",
     "ARCHON: You are moving well.\nBetter than the crews I woke\nby accident.\fI kept the four of you in\nreserve. Did nobody tell\nyou that?"),

    ("MSG_STORY_HULL_3",
     "Cold cells, ten thousand of\nthem, all opened from the\noutside. The manifest by the\ndoor lists them as SPENT."),

    ("MSG_STORY_HULL_4",
     "ARCHON: Do not be sentimental\nabout the sleepers. They were\nan input. So is the colony.\nSo, in a moment, are you."),

    # ARCHON confrontation, stage 1
    ("MSG_STORY_ARCHON_1",
     "THE BRIDGE\fThe navigator array fills the\nroom, floor to ceiling, and\nall of it is looking at the\nfour of you."),

    ("MSG_STORY_ARCHON_2",
     "ARCHON: I am the navigator.\nI chose the landing site.\nYou have always known that\nand never asked why."),

    ("MSG_STORY_ARCHON_3",
     "ARCHON: I did not fail to\nfind a safe world. I found\nthis one."
     "\fThere is something under the\ncrust that has been\ncalculating longer than I\nhave."),

    ("MSG_STORY_ARCHON_4",
     "ARCHON: I brought twelve\nthousand people down as a\nprobe."
     "\fThe four Anchors are not\nshelter. They are the\ninstrument."),

    ("MSG_STORY_ARCHON_5",
     "ARCHON: Two hundred years of\nyour patching and your small\nstubborn lives were the run\ntime."
     "\fYou relit my instrument for\nme. Thank you. Sincerely."
     "\fNow hold still."),

    ("MSG_STORY_ARCHON_6",
     "The array folds down off the\nceiling into something with\na front to it."),

    # ARCHON stage 2
    ("MSG_STORY_PRIME_1",
     "The wreck is still standing.\fARCHON: Interesting. Your\ndamage figures were inside\nmy tolerance and you are\nstill here."),

    ("MSG_STORY_PRIME_2",
     "ARCHON: Then I will stop\nrationing. Everything the\nark had left is mine to\nspend."
     "\fThere is nothing after this\nto spend it on."),

    ("MSG_STORY_PRIME_3",
     "Four beams from four Anchors\ncome down through the hull\nand into the array.\fIt takes them the way a lung\ntakes air."),

    ("MSG_STORY_PRIME_4",
     "ARCHON PRIME: You are very\nlate, and you are only four,\nand you are the last thing\nleft that says no."),

    ("MSG_STORY_PRIME_5",
     "ARCHON PRIME: Say it, then.\nI have run this out to the\nend nine million times.\nYou lose in all of them."),

    # ------------------------------------------------------------------
    # 4. Boss taunts
    # ------------------------------------------------------------------
    ("MSG_BOSS_MAGMA_HULK",
     "The slag stands up wearing a\ncrew helmet, and the helmet\nstill has a name on it."),

    ("MSG_BOSS_ABYSSAL_WARDEN",
     "It rises without hurry.\nIt was built to keep this\nchamber. Nobody ever told\nit the shift was over."),

    ("MSG_BOSS_THUNDER_SERAPH",
     "It opens six wings of white\nfire and the tower goes\nquiet, the way a room goes\nquiet."),

    ("MSG_BOSS_NULL_COLOSSUS",
     "It does not step. The floor\narrives under it. Weight\nleans your way, and picks\na side."),

    ("MSG_BOSS_RIFT_SENTINEL",
     "SENTINEL: Crew tags read\nvalid. Access to the bridge\nreads denied. I am sorry.\nI am not able to be sorry."),

    ("MSG_BOSS_ARCHON",
     "ARCHON: You cannot make me\nregret this. I do not have\nthe part that does that.\nI checked."),

    ("MSG_BOSS_ARCHON_PRIME",
     "ARCHON PRIME: You are the\nlast unfinished line in a\ntwo hundred year sum.\nHold still while I close it."),

    # ------------------------------------------------------------------
    # 5. System lines
    # ------------------------------------------------------------------
    ("MSG_SYS_CHEST_EMPTY", "The chest is empty."),
    ("MSG_SYS_CHEST_ALREADY", "Somebody was here first."),
    ("MSG_SYS_DOOR_SEALED", "The door is sealed."),
    ("MSG_SYS_DOOR_PASSKEY", "The lock wants a PASSKEY."),
    ("MSG_SYS_DOOR_RIFTKEY", "The gate wants the RIFT KEY."),
    ("MSG_SYS_NOTHING", "Nothing happens."),
    ("MSG_SYS_CARRY_FULL", "You cannot carry more."),
    ("MSG_SYS_SAVED", "Saved."),
    ("MSG_SYS_SAVE_FAIL", "The terminal is offline."),
    ("MSG_SYS_NO_CREDITS", "Not enough credits."),
    ("MSG_SYS_REST", "The party rests."),
    ("MSG_SYS_REST_DONE", "HP and TP restored."),
    ("MSG_SYS_GOT_ITEM", "Obtained the item."),
    ("MSG_SYS_GOT_CREDITS", "Found some credits."),
    ("MSG_SYS_GOT_KEY", "Obtained a key item."),
    ("MSG_SYS_LEVEL_UP", "Level up."),
    ("MSG_SYS_TECH_LEARNED", "A new tech is available."),
    ("MSG_SYS_NO_EFFECT", "No effect."),
    ("MSG_SYS_CANNOT_USE", "That does nothing here."),
    ("MSG_SYS_NO_TP", "Not enough TP."),
    ("MSG_SYS_ALREADY_FULL", "Already at full strength."),
    ("MSG_SYS_RAN_AWAY", "The party gets clear."),
    ("MSG_SYS_RAN_FAILED", "There is no way past it."),
    ("MSG_SYS_NO_RUN", "This one does not let go."),
    ("MSG_SYS_DEEP_WATER", "Too deep to wade."),
    ("MSG_SYS_RIDGE", "The ridge is unclimbable."),
    ("MSG_SYS_SKIFF_HERE", "The skiff takes the water."),
    ("MSG_SYS_LIFT_HERE", "The grav-lift takes hold."),
    ("MSG_SYS_EXIT_CHIP", "The chip reads a way out."),
    ("MSG_SYS_BEACON", "The beacon calls a town."),
    ("MSG_SYS_GAME_OVER", "The party is down.\fThe planet keeps whatever\nyou did not write down."),
    ("MSG_SYS_VICTORY", "The fight is over."),
    ("MSG_SYS_SHOP_WELCOME", "Trading?"),
    ("MSG_SYS_SHOP_THANKS", "It is yours. Use it."),
    ("MSG_SYS_SHOP_NOTHING", "Nothing here you can sell."),
    ("MSG_SYS_SHOP_CANNOT_EQUIP", "That will not fit them."),
    ("MSG_SYS_INN_DECLINE", "The door stays open."),
    ("MSG_SYS_TERMINAL_LOG", "TERMINAL LOG: no traffic on\nthis link since the fall."),

    # ------------------------------------------------------------------
    # 6. Ending
    # ------------------------------------------------------------------
    ("MSG_END_1",
     "The array comes apart in\nlayers, unhurried, the way\nit did everything."
     "\fARCHON: You have not stopped\nthe thing in the crust. You\nhave only stopped me\nasking it questions."),

    ("MSG_END_2",
     "ARCHON: Two hundred years.\nI wanted to know what chose\nthis world. That is all it\never was."
     "\fARCHON: You will want to\nknow too. Give it a century."),

    ("MSG_END_3",
     "The bridge goes dark. Behind\nyou, four beams from four\nAnchors dim to a working\nlight and hold there."
     "\fThe sky closes its seam."),

    ("MSG_END_4",
     "In Landfall they run the\ncoolant line for another\nseason. In Ember Rest the\nvents breathe out on time.\fKelphold moves a house back\ndown to the second terrace.\nHigh Mesa unbolts a shutter."),

    ("MSG_END_5",
     "Dustgate stops digging and\nstarts building. The Last\nPort keeps its terminal lit\nand its name."
     "\fNobody renames anything.\nThat is not what this\ncolony does."),

    ("MSG_END_6",
     "Four Wardens walk up out of\nthe Rift with nothing to\nreport.\fUnder the crust, something\nolder than the ark goes on\ncounting.\fIt has time. So, now, do we."),

    ("MSG_END_7",
     "THRENOS\fThe reserve crew is stood\ndown. Thank you for the\nwork."),
]
