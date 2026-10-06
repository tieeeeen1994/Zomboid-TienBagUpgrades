# Tien's Bag Upgrades — working notes

Derivative of Dynamic Backpack Upgrades by Dr. Lalaoz, Harrod200 and Lenniitsch (https://steamcommunity.com/sharedfiles/filedetails/?id=2996978365); every public text
(README, mod.info, a future workshop.txt) must say so plainly, with the link and the list of what is taken. Original: workshop 2996978365, mod id LazoloDynamicBackpackUpgrades, 42.20
folder; its Hide & Tarp Fanny Packs extension (3801558401) is folded in. Engine findings live in
`~/Zomboid/Workshop/ZomboidFixesB42/CLAUDE.md` (bag capacity / weight reduction serialization is under
"Bag max item size"); only what is specific to this mod is here. Checked against 42.21.

## Drop-in compatibility (do not rename)

- Item module `DynamicBackpacks`, the eight `Upgrade*` item names, recipe module `DynamicBackpackRecipes`
  and recipe names, sandbox options `DynamicBackpacks.*` (names, types, defaults, min/max). Renaming an
  option resets it on existing servers. `DynamicBackpacks.SewingXP` is ours alone (the old mod has no such option); on a
  server coming from the old mod it starts at its default, 0.
- Bag modData keys: `LUpgrades` (list of short item types), `LCapacity` / `LWeightReduction` (stats before
  upgrades), `LDynamicBackpacksInit`, and for going back to the old mod `LComputedCapacity` / `LComputedWeightReduction`,
  `LMaxUpgrades` (base + location modifier, no Tailoring) and `LFixState`: the old mod skips its own setup on a bag
  marked `LDynamicBackpacksInit` and its tooltip errors on `LMaxUpgrades > 0` when that is nil.
- The stats formula must stay bit-identical to the old `DBU.GetUpgradedStats`, including its float
  quirk: the capacity share is `floor(base * ((1 + p) - 1))`, so 5 * 0.2 gives 0. Checked over 36000
  cases (bases 1-40, WR 0-95, every pair of upgrades) with lupa against a copy of the old function.
- `mod.info` declares `incompatible=` with both old mods.

## What the old mod got wrong (why this exists)

- It believed capacity is not saved, so it re-applied stats from modData every game minute
  (`EveryOneMinute` InvCheck), on every tooltip frame and every context menu, and wrote modData onto
  every bag hovered. Capacity and WR are saved and sent with the item; only SyncItemFields lacks them.
- Its "Fix" menu called `DBU.UpdateBag(item)` on the client only.
- Recipes used `flags[IsEmptyContainer]` (only logs; contents deleted). `flags[IsEmpty]` refuses a
  non-empty `InventoryContainer` and does nothing to plain items (`InputScript.doesItemPassIsOrNotEmptyAndFullTests`).
- Recipe translation keys were `Recipe_Make_...`; B42 looks up the recipe name itself (`ClothBagUpgrade`).
- Loot weights were read at file load, before sandbox values exist.
- Two debug test files shipped, one registering an `OnTick` handler for the whole session.

## How it works

- `shared/TienBagUpgrades/TienBagUpgrades_Shared.lua`: rules (slots, formula, clamp to
  `min(50, floor(50 - bag weight))`, remove check, tools), `TBU.apply` (server / SP: set stats, send
  `bagStats {id, capacity, weightReduction, baseCapacity, baseWeightReduction, upgrades}` to the owner).
- `shared/TimedActions/TienBag{Add,Remove}UpgradeAction.lua`: built like vanilla `ISRepairClothing`
  (client refreshes item objects by ID in `start`, server re-checks in `complete` and returns false to
  Reject). Add: needle + 1 thread use, `150 - Tailoring * 6`. Remove: scissors (or sharp knife option),
  `100 - Tailoring * 4`, refused while the contents would not fit. Adding gives sandbox `DynamicBackpacks.SewingXP` Tailoring
  XP (our own option, default 0; `addXp`, as `ISRepairClothing` gives 2); removing gives none, since it always returns the item (vanilla's `ISRemovePatch` gives 2
  only when the fabric comes back), so a sew / cut loop yields SewingXP per thread use.
- `client/.../TienBagUpgrades_Client.lua`: menus (read only), `bagStats` handler writes the client's copy.
- `client/.../TienBagUpgrades_Tooltip.lua`: after the whole render chain, extends the panel down (paints over
  the old bottom border, redraws the border), draws the lines, then sets the ObjectTooltip's height to the panel's
  so Plysken Attachments Reborn's slot box (drawn next frame at `tooltip:getHeight()`) starts below them, in either
  load order. No method swapping (that broke when Plysken's own `setHeight` call came first). Lines cached per item
  + numbers.
- `server/.../TienBagUpgrades_Server.lua`: loot at `OnPreDistributionMerge`; `IsoWorld.init` fires the
  merge events **before** `SandboxOptions.load` and then `ItemPickerJava.Parse` with no event between, so
  `OnInitGlobalModData` rewrites the entries and calls `IsoWorld.parseDistributions()` (Parse +
  InitSandboxLootSettings) only when a loot multiplier differs. `EveryTenMinutes` re-applies the bags
  each player carries once per stats-settings signature (and once per player after a restart).

## Art

- Item icons (`media/textures/Item_Upgrade*.png`) and `icon.png` (= the military pouch icon) are rendered from our
  dropped models by `scripts/make_models.py` (`icon_from_model`): the model at 384 px, cropped, shrunk to fit 30 px
  (premultiplied LANCZOS), alpha cut at 110, contrast 1.15 and colour 1.1, a 1 px near-black outline like vanilla
  icons. Pouch at yaw 40 / pitch 38; the strap is rendered from a coiled copy of its mesh (`build_strap(coiled=True)`,
  a 230° C, written to `tmp/` only) at yaw 30 / pitch 58, since the straight strap is a thin diagonal at 32 px.
  `--preview` writes `tmp/icons_preview.png` beside vanilla's fanny pack and belt.
- `poster.png` / `preview.png`: `scripts/make_poster.py` (run after make_models.py), the series' sticker look on a pink
  glow (248,178,206 to 190,92,140), whole-number pixel stickers with a white outline and soft shadow, no text): the game's `Item_AliceBag`,
  `Item_Thread`, `Item_Needle`, our denim pouch and leather strap icons, a yellow up arrow. No art from Dynamic
  Backpack Upgrades is shipped any more.

## Dropped models

`scripts/make_models.py` (`--preview` renders `tmp/models_preview.png` with `scripts/pz_model.py`, the software
renderer from TienCoolers) builds both meshes vertex by vertex and writes
`media/models_X/WorldItems/TienBagUpgrades_{Pouch,Strap}.fbx` and 8 textures (128 px) in `media/textures/WorldItems/`;
the item script defines `TienBagUpgrades_{Pouch,Strap}<Mat>_Ground` (scale 0.4 both) and points each item's
`WorldStaticModel` at its own.

- Each FBX is vanilla `M_FannyPackFront_Ground.fbx` with only the Geometry node replaced (`scripts/fbx_bin.py`
  reads and writes binary FBX as a node tree; an untouched file round-trips byte for byte). So it keeps that file's
  3ds Max header (UpAxis Y, OriginalUpAxis Z, UnitScaleFactor 91.44), the model's PreRotation -90 X / Lcl Rotation
  +90 X / Lcl Scaling 1/36 and its material, and the game treats it like the fanny pack. Vertices are in that raw
  frame: Z up, ground at z = 0, units where the fanny pack is 18 x 16 x 6 (pouch 13.6 x 15.4 x 6, strap 35.7 x 9.2
  x 1.6).
- Geometry written: Vertices, PolygonVertexIndex (quads and triangles; the game's importer triangulates),
  normals ByPolygonVertex Direct (smooth within a part, hard between parts; every hardware face flat), one UV set
  ByPolygonVertex IndexToDirect (FBX v up; the game uses 1 - v, texel row = (1 - v) * height), material AllSame.
  Winding is counter-clockwise around the outward normal, as in every vanilla world mesh checked; the checks in
  this session tested every part's faces against its centre (the strip quads are built clockwise and reversed).
- Blender 5.2 imports both exactly like the vanilla file (same 0.0254 scale, no rotation), checked headless.
- Pouch texture layout: front 0,0-64,64 (back half under the flap), flap 64,0-128,40, flap edge 64,40-128,48,
  tab 64,48-96,64 (top half: snap), bottom 96,48-128,64, sides 0,64-128,96, bevels 0,96-128,112.
- Strap: one strip along a gentle S (arc-length parametrised), 6 segments across a domed profile, 48 stations;
  width 2.6 / thickness 0.35 for webbing, 5.4 / 1.6 for the pad between 22% and 78% of the length; ladder-lock
  buckle (4 bars + middle bar) past the first end, a ring past the other. Texture: the strip runs along x (buckle
  end at 0), top 0-48, sides 48-56, underside 56-72, end caps 0,72-32,80, hardware 0,96-64,128 (top half lit
  gradient, bottom half shade); pad in the material with bound edges and quilting, webbing elsewhere, box-X
  stitches where they meet.
