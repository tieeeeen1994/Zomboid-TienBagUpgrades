# Tien's Bag Upgrades

Sew capacity upgrades and weight-reduction straps onto your bags.

**This mod is a derivative of [Dynamic Backpack Upgrades](https://steamcommunity.com/sharedfiles/filedetails/?id=2996978365) by Dr. Lalaoz, Harrod200 and
Lenniitsch.** It is not an original design: the idea, the upgrade items, the recipes, the sandbox
options, the stats formula and the loot tables come from that mod; the code, the dropped item models, the item icons and the poster are new. See [Credits](#credits).

## Why a separate mod

Dynamic Backpack Upgrades had performance trouble and bag stats that kept reverting, so its code was
rewritten from scratch. Before anything else, the point is to find out in real games whether the new
code is actually better or worse, and a separate mod does that without touching the original:

- Dynamic Backpack Upgrades stays exactly as it is, for everyone who uses it.
- This version can be tried on the same save, and the save can go back to Dynamic Backpack Upgrades
  if it plays worse: both read the same items, settings and upgrade data, so upgraded bags carry
  over either way.
- Bug reports and comparisons with the original are welcome.

## Replacing Dynamic Backpack Upgrades

It replaces Dynamic Backpack Upgrades in
existing saves: the upgrade items, recipes and sandbox settings keep their names, and bags already
upgraded keep their upgrades and their numbers. Unsubscribe from Dynamic Backpack Upgrades (and its
Hide & Tarp Fanny Packs extension, now built in) before enabling this mod.

## How it plays

- **Right-click a bag**: *Add Upgrade* lists the upgrade items you carry; *Remove Upgrade* cuts one
  off and gives the item back. Adding takes a sewing needle and one use of thread, and gives Tailoring XP if the server
  sets some (off by default); removing takes
  scissors (or a sharp knife, if the sandbox allows it).
- **Right-click an upgrade item**: *Sew onto Bag* lists the bags in your inventory with their free
  slots, bags inside other bags included.
- **Bag upgrades** (cloth, denim, leather, military) add a share of the bag's original capacity
  plus a flat amount. **Straps** remove a share of the weight the bag does not already reduce.
- **Slots**: every container item counts as a bag (backpacks, fanny packs, handbags, toolboxes,
  wallets, keyrings...). Each has the base slots, plus a modifier for back bags, fanny packs and
  other bags, plus one slot every few Tailoring levels.
- **Crafting**: the upgrade items are sewn from fanny packs (regular, Hide and Tarp), belts,
  ripped sheets, denim and leather strips, in the Tailoring category. A fanny pack with anything in
  it is no longer accepted (Dynamic Backpack Upgrades deleted its contents).
- **Dropped items** have their own models: a padded pouch for each bag upgrade and a padded shoulder
  strap with its buckle for each straps upgrade, in the material's colours.
- **Tooltips** show a bag's slots and what its upgrades add, and what an upgrade item does with the
  current settings. A bag holds up to 50; the tooltip says so when an upgrade goes past it. The
  game's own Capacity line takes the bag's weight off that (a Large Framepack shows 46) without
  enforcing it, so the tooltip also gives the real capacity when the two differ.

## What changed from Dynamic Backpack Upgrades

- Stats are set once, by the server, when an upgrade goes on or comes off, and are saved with the
  bag. Nothing re-checks your inventory every minute or every tooltip frame, hovering a bag no
  longer writes data onto it, and there is no "Fix Upgrades" menu because stats no longer drift.
- In multiplayer the server checks everything again before it changes anything, and sends the new
  stats to your client straight away.
- The plain Key Ring takes upgrades too (Dynamic Backpack Upgrades banned that one item type; its
  decorated variants were already allowed).
- Loot multipliers follow the sandbox settings (they were read before the settings existed).
- Sewing uses the vanilla sewing animation and sound and takes as long as patching clothing
  (faster with Tailoring).
- Changing the upgrade strength settings re-applies the bags players carry within ten in-game
  minutes. Bags lying in the world are updated the next time an upgrade goes on or comes off.

## Sandbox options (page "Bag Upgrades")

Same names and defaults as Dynamic Backpack Upgrades: Knives Remove Upgrades (off), Base Upgrade
Slots (1), Back Bag / Fanny Pack / Other Bag Slot Modifiers (+1 / 0 / 0), Tailoring Levels per
Extra Slot (10), and for each material a capacity share, a flat capacity bonus, a weight reduction
share and a loot multiplier. New here: Tailoring XP for Sewing On an Upgrade (0, off by default;
patching clothing gives 2).

## Credits

This mod is a derivative work of **Dynamic Backpack Upgrades** by Dr. Lalaoz, Harrod200 and
Lenniitsch: https://steamcommunity.com/sharedfiles/filedetails/?id=2996978365

Taken from Dynamic Backpack Upgrades:

- the idea of sewing capacity upgrades and weight-reduction straps onto bags, with upgrade slots
  per bag and extra slots from Tailoring;
- the eight upgrade items (module and item names, weights, display names);
- the eight crafting recipes (names, ingredients, skill levels);
- the sandbox options (names, ranges, defaults);
- the stats formula, kept identical so its saves load with the same numbers;
- the loot tables and their weights;
- the names of the data stored on upgraded bags.

Written anew for this mod: all of the Lua code, the dropped item models (a pouch and a padded strap, with
their textures), the item icons and mod icon, rendered from those models,
and the poster, which also uses the game's ALICE pack, thread and needle icons. No art from Dynamic
Backpack Upgrades is used. The Hide and Tarp fanny pack recipe inputs come from
Dynamic Backpack Upgrades - Hide & Tarp Fanny Packs, Tien's own extension of the original.
