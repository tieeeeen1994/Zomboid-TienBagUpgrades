--[[
    Tien's Bag Upgrades - shared rules.

    A stand-alone rework of Dynamic Backpack Upgrades that loads its saves: same item, recipe and
    sandbox option names, and a bag keeps its upgrades in its modData under that mod's keys:
        LUpgrades                  list of upgrade item types ("UpgradeCapacityCloth", ...)
        LCapacity, LWeightReduction the bag's stats before any upgrade
        LComputedCapacity, LComputedWeightReduction  kept up to date so a save can go back to that mod

    Capacity and weight reduction are saved with the bag and travel in every copy of the item the
    server sends (ItemContainer.save writes the capacity, InventoryContainer.save the weight
    reduction), so they only have to be set once, by the server (or single player) in the timed
    actions' complete(). Only the live item sync (SyncItemFieldsPacket) leaves them out, so the
    server tells the owner's client the new values itself (TienBagUpgrades.apply, "bagStats").

    The engine caps a bag's capacity at 50 and at 50 minus the bag's own weight
    (InventoryContainer.getCapacity); the stats are clamped to that before they are set.
]]

TienBagUpgrades = TienBagUpgrades or {}
local TBU = TienBagUpgrades

TBU.MODULE = "TienBagUpgrades"
TBU.ITEM_MODULE = "DynamicBackpacks"
TBU.CMD_BAG_STATS = "bagStats"

-- Upgrade item type -> what it changes and which sandbox options set its strength.
TBU.UPGRADES = {
    UpgradeCapacityCloth = { capacity = true, material = "Cloth" },
    UpgradeCapacityJean = { capacity = true, material = "Jean" },
    UpgradeCapacityLeather = { capacity = true, material = "Leather" },
    UpgradeCapacityMilitary = { capacity = true, material = "Military" },
    UpgradeWeightReductionCloth = { capacity = false, material = "Cloth" },
    UpgradeWeightReductionJean = { capacity = false, material = "Jean" },
    UpgradeWeightReductionLeather = { capacity = false, material = "Leather" },
    UpgradeWeightReductionMilitary = { capacity = false, material = "Military" },
}

-- Menu order.
TBU.UPGRADE_ORDER = {
    "UpgradeCapacityCloth", "UpgradeCapacityJean", "UpgradeCapacityLeather", "UpgradeCapacityMilitary",
    "UpgradeWeightReductionCloth", "UpgradeWeightReductionJean", "UpgradeWeightReductionLeather",
    "UpgradeWeightReductionMilitary",
}

local DEFAULTS = {
    KnivesCanRemove = false,
    BaseUpgradeSlots = 1, BackSlotModifier = 1, FannySlotModifier = 0, OtherSlotModifier = 0, TailoringModifier = 10,
    SewingXP = 0,
    ClothCapacityPercentage = 0.1, ClothCapacityBonus = 1, ClothReductionPercentage = 0.15, ClothLootSpawns = 1,
    JeanCapacityPercentage = 0.2, JeanCapacityBonus = 1, JeanReductionPercentage = 0.25, JeanLootSpawns = 1,
    LeatherCapacityPercentage = 0.25, LeatherCapacityBonus = 2, LeatherReductionPercentage = 0.35, LeatherLootSpawns = 1,
    MilitaryCapacityPercentage = 0.35, MilitaryCapacityBonus = 2, MilitaryReductionPercentage = 0.5, MilitaryLootSpawns = 1,
}

-- Sandbox option of the DynamicBackpacks page (the old mod's names, so servers keep their settings).
function TBU.opt(name)
    local vars = SandboxVars and SandboxVars.DynamicBackpacks
    local value = vars and vars[name]
    if value == nil then return DEFAULTS[name] end
    return value
end

local function round(x)
    return math.floor(x + 0.5)
end

function TBU.fullType(upgradeType)
    return TBU.ITEM_MODULE .. "." .. upgradeType
end

-- The upgrade entry of an upgrade item (or of its type), nil for anything else.
function TBU.upgradeInfo(itemOrType)
    if type(itemOrType) == "string" then return TBU.UPGRADES[itemOrType] end
    if not itemOrType then return nil end
    local upgradeType = itemOrType:getType()
    local info = TBU.UPGRADES[upgradeType]
    if info and itemOrType:getFullType() == TBU.fullType(upgradeType) then return info end
    return nil
end

function TBU.upgradeName(upgradeType)
    local script = getScriptManager():getItem(TBU.fullType(upgradeType))
    return script and script:getDisplayName() or upgradeType
end

-- Every container item takes upgrades (keyrings, wallets and toolboxes too); how many depends on where
-- it is worn (TBU.baseSlots). Dynamic Backpack Upgrades banned only the plain KeyRing type (an exact
-- getType() match, so its 28 decorated KeyRing_* variants were allowed); this mod bans none.
function TBU.isBag(item)
    return item ~= nil and item:IsInventoryContainer()
end

-- The bag's upgrade list, or nil when it has none. Never creates modData.
function TBU.getUpgrades(bag)
    if not bag:hasModData() then return nil end
    local list = bag:getModData().LUpgrades
    if type(list) ~= "table" or #list == 0 then return nil end
    return list
end

function TBU.countUpgrades(bag)
    local list = TBU.getUpgrades(bag)
    return list and #list or 0
end

-- Upgrade slots of a bag for this player: base + the bag's body location modifier, plus one every
-- TailoringModifier Tailoring levels (0 = none). A bag left with no base slots takes no upgrades.
-- Base slots plus the body location modifier, before Tailoring; may be 0 or negative.
function TBU.baseSlots(bag)
    local location = bag:canBeEquipped()
    local modifier
    if location == ItemBodyLocation.BACK then
        modifier = TBU.opt("BackSlotModifier")
    elseif location == ItemBodyLocation.FANNY_PACK_BACK or location == ItemBodyLocation.FANNY_PACK_FRONT then
        modifier = TBU.opt("FannySlotModifier")
    else
        modifier = TBU.opt("OtherSlotModifier")
    end
    return TBU.opt("BaseUpgradeSlots") + modifier
end

function TBU.maxSlots(bag, player)
    local slots = TBU.baseSlots(bag)
    if slots <= 0 then return 0 end
    local every = TBU.opt("TailoringModifier")
    if every > 0 and player then
        slots = slots + math.floor(player:getPerkLevel(Perks.Tailoring) / every)
    end
    return slots
end

function TBU.hasFreeSlot(bag, player)
    return TBU.countUpgrades(bag) < TBU.maxSlots(bag, player)
end

-- The bag's stats before upgrades.
function TBU.baseStats(bag)
    local md = bag:hasModData() and bag:getModData() or nil
    local capacity = md and tonumber(md.LCapacity) or bag:getCapacity()
    local reduction = md and tonumber(md.LWeightReduction) or bag:getWeightReduction()
    return capacity, reduction
end

-- Largest capacity the engine lets this bag have.
function TBU.capacityCap(bag)
    return math.min(50, math.floor(50 - bag:getActualWeight()))
end

-- Same formula as Dynamic Backpack Upgrades, so its bags keep their numbers: each capacity upgrade
-- adds a share of the base capacity plus a flat bonus; each strap multiplies what the bag does not
-- yet reduce.
function TBU.computeStats(baseCapacity, baseReduction, upgrades)
    local bonus, keep = 0, 1
    for i = 1, #upgrades do
        local info = TBU.UPGRADES[upgrades[i]]
        if info then
            if info.capacity then
                -- (1 + p) - 1 rather than p, as Dynamic Backpack Upgrades computed it: the float error
                -- rounds some shares down (5 * 0.2 gives 0), and its bags must keep their numbers.
                local share = (1 + TBU.opt(info.material .. "CapacityPercentage")) - 1
                bonus = bonus + math.floor(baseCapacity * share) + TBU.opt(info.material .. "CapacityBonus")
            else
                keep = keep * (1 - TBU.opt(info.material .. "ReductionPercentage"))
            end
        end
    end
    local capacity = math.max(0, round(baseCapacity + bonus))
    local reduction = math.max(0, math.min(100, round(100 - (100 - baseReduction) * keep)))
    return capacity, reduction
end

-- Stats the bag should have now, clamped like the engine clamps them.
function TBU.targetStats(bag)
    local baseCapacity, baseReduction = TBU.baseStats(bag)
    local capacity, reduction = TBU.computeStats(baseCapacity, baseReduction, TBU.getUpgrades(bag) or {})
    return math.min(capacity, TBU.capacityCap(bag)), reduction, capacity
end

-- Can this upgrade come off? A capacity upgrade cannot while the bag holds more than it would hold
-- without it. Returns ok, contents weight, capacity without it.
function TBU.removeCheck(bag, upgradeType)
    local info = TBU.UPGRADES[upgradeType]
    if not info or not info.capacity then return true end
    local remaining, removed = {}, false
    for _, t in ipairs(TBU.getUpgrades(bag) or {}) do
        if t == upgradeType and not removed then
            removed = true
        else
            remaining[#remaining + 1] = t
        end
    end
    local baseCapacity, baseReduction = TBU.baseStats(bag)
    local capacity = TBU.computeStats(baseCapacity, baseReduction, remaining)
    capacity = math.min(capacity, TBU.capacityCap(bag))
    local weight = bag:getContentsWeight()
    return weight <= capacity + 0.001, weight, capacity
end

-- Text describing what an upgrade type does with the current settings.
function TBU.describeUpgrade(upgradeType)
    local info = TBU.UPGRADES[upgradeType]
    if not info then return nil end
    if info.capacity then
        local percent = round(TBU.opt(info.material .. "CapacityPercentage") * 100)
        local flat = TBU.opt(info.material .. "CapacityBonus")
        local text = getText("IGUI_TienBagUpgrades_EffectCapacity", string.format("%d", percent))
        if flat ~= 0 then text = text .. " " .. (flat > 0 and "+" or "") .. string.format("%d", flat) end
        return text
    end
    local percent = round(TBU.opt(info.material .. "ReductionPercentage") * 100)
    return getText("IGUI_TienBagUpgrades_EffectReduction", string.format("%d", percent))
end

---------------------------------------------------------------------------------------------------
-- Tools
---------------------------------------------------------------------------------------------------

local function threadHasUses(item)
    return item:getCurrentUses() > 0
end

local function notBroken(item)
    return not item:isBroken()
end

function TBU.findNeedle(inventory)
    return inventory:getFirstTagRecurse(ItemTag.SEWING_NEEDLE)
end

function TBU.findThread(inventory)
    return inventory:getFirstTypeEvalRecurse("Base.Thread", threadHasUses)
end

function TBU.findCutter(inventory)
    local tool = inventory:getFirstTagEvalRecurse(ItemTag.SCISSORS, notBroken)
    if not tool and TBU.opt("KnivesCanRemove") then
        tool = inventory:getFirstTagEvalRecurse(ItemTag.SHARP_KNIFE, notBroken)
    end
    return tool
end

function TBU.isCutter(item)
    if not item or item:isBroken() then return false end
    if item:hasTag(ItemTag.SCISSORS) then return true end
    return TBU.opt("KnivesCanRemove") == true and item:hasTag(ItemTag.SHARP_KNIFE)
end

---------------------------------------------------------------------------------------------------
-- Applying stats
---------------------------------------------------------------------------------------------------

-- Records the base stats before the first upgrade goes on.
function TBU.ensureBase(bag)
    local md = bag:getModData()
    if type(md.LUpgrades) ~= "table" then md.LUpgrades = {} end
    if md.LCapacity == nil then md.LCapacity = bag:getCapacity() end
    if md.LWeightReduction == nil then md.LWeightReduction = bag:getWeightReduction() end
    -- Dynamic Backpack Upgrades skips its own setup on a bag marked LDynamicBackpacksInit and then
    -- reads these two (its tooltip compares LMaxUpgrades with 0), so a bag first upgraded here must
    -- have them for a save to go back to that mod.
    md.LMaxUpgrades = TBU.baseSlots(bag)
    if md.LFixState == nil then md.LFixState = "Show" end
    md.LDynamicBackpacksInit = true
    return md
end

-- Writes stats (and the upgrade list) onto a bag. Used by the server / single player and by the
-- client when the server's "bagStats" arrives.
function TBU.setStats(bag, capacity, reduction)
    bag:setCapacity(capacity)
    bag:setWeightReduction(reduction)
    local md = bag:getModData()
    md.LComputedCapacity = bag:getCapacity()
    md.LComputedWeightReduction = bag:getWeightReduction()
end

-- Server / single player: sets the bag's stats from its upgrades and tells the owner's client.
function TBU.apply(bag, player)
    local md = TBU.ensureBase(bag)
    local capacity, reduction = TBU.targetStats(bag)
    TBU.setStats(bag, capacity, reduction)
    if isServer() and player then
        local list = {}
        for i = 1, #md.LUpgrades do list[i] = md.LUpgrades[i] end
        sendServerCommand(player, TBU.MODULE, TBU.CMD_BAG_STATS, {
            id = bag:getID(),
            capacity = capacity,
            weightReduction = reduction,
            baseCapacity = md.LCapacity,
            baseWeightReduction = md.LWeightReduction,
            upgrades = list,
        })
    end
end

-- Server / single player: re-applies the stats when they no longer match the upgrades (sandbox
-- values changed, or a bag left out of step by Dynamic Backpack Upgrades). Returns true if it did.
function TBU.refresh(bag, player)
    if not TBU.getUpgrades(bag) then return false end
    local capacity, reduction = TBU.targetStats(bag)
    if bag:getCapacity() == capacity and bag:getWeightReduction() == reduction then return false end
    TBU.apply(bag, player)
    return true
end

-- The settings the stats depend on, to notice a change.
function TBU.statsSignature()
    local parts = {}
    for _, material in ipairs({ "Cloth", "Jean", "Leather", "Military" }) do
        parts[#parts + 1] = tostring(TBU.opt(material .. "CapacityPercentage"))
        parts[#parts + 1] = tostring(TBU.opt(material .. "CapacityBonus"))
        parts[#parts + 1] = tostring(TBU.opt(material .. "ReductionPercentage"))
    end
    return table.concat(parts, ";")
end
