# TODO

## Before publishing

- Look at the item icons in game, in the inventory at 1x and with large UI, next to vanilla bags and belts.
- workshop.txt: written; set visibility to public (now private) once the in-game tests pass.
- Translations other than EN.

## In-game tests (not played yet)

Single player (`-debug` for spawning items):
1. Spawn a Military Bag Upgrade, a needle, thread, scissors and an ALICE pack. Right-click the pack:
   Add Upgrade lists the upgrade; sew it on. Tooltip shows slots 1/2 and the added capacity, capped
   when it passes 50 minus the bag's weight.
   With SewingXP at 0 (default) Tailoring XP does not change; set it to 2 and it goes up by 2 per upgrade
   sewn on, and not when one is cut off.
2. Right-click the upgrade item instead: Sew onto Bag lists the bags with used/max slots; full bags greyed.
3. Fill the upgraded bag past its original capacity: Remove Upgrade on the capacity upgrade is greyed
   with the weights; straps can still come off. Empty it and remove: the item comes back, stats return.
4. Save, quit, reload: stats are kept with no menu touched.
5. Load a save made with Dynamic Backpack Upgrades: upgraded bags show the same capacity / WR, their
   upgrades can be removed.
5b. Going back: upgrade a fresh bag with this mod, save, switch the save to Dynamic Backpack Upgrades:
   the bag keeps its stats, its tooltip shows the upgrades without errors, and they can be removed there.
5c. Drop one of each of the 8 items: each shows its own pouch or padded strap model in its material, lying flat
   on the ground at a sensible size next to a vanilla fanny pack and belt (the strap about twice a fanny pack's width), textured the right way up, no faces missing.
5d. With Plysken Attachments Reborn, loaded before this mod and then after it: hover an upgraded backpack that
   has attachment slots; the upgrade lines sit right under the bag's text and Plysken's attachment slot box under
   them, nothing overlapping, in both orders.
6. Craft a Cloth Bag Upgrade with a fanny pack holding an item: the full pack is not accepted.
   Hide and Tarp fanny packs are accepted; recipe names show translated.
7. Change ClothCapacityPercentage mid-game: within ten in-game minutes the carried cloth-upgraded bags change.

Multiplayer (`TienGiveItemMP/scripts/mptest.sh`):
8. Steps 1 and 3 on a client: the client's copy shows the new stats right after the action; the
   server log has no errors; a second client sees nothing odd.
9. On a bag with one free slot, queue two upgrades: the second does not start and uses no thread.
10. Revert check (the old mod's bug): upgrade a bag past the 50-minus-weight cap, then drop it, pick it up,
    move it between containers, equip and unequip it, wait a few in-game hours and hover it. Capacity
    and WR never change, and the server log has no "Attempting to set capacity" lines after the first.
11. Set a loot multiplier to 0 in the server's sandbox file: no upgrades in army surplus stores.
