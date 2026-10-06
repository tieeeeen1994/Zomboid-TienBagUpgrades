--[[
    Tien's Bag Upgrades - loot and keeping stats in step with the settings (server / single player).

    Loot: the upgrade items join the procedural lists Dynamic Backpack Upgrades used, at its weights
    times the material's LootSpawns option. IsoWorld.init fires the distribution merge events before
    it loads the save's sandbox options (SandboxOptions.load) and then parses the lists
    (ItemPickerJava.Parse), with no event in between, so the weights are written at
    OnPreDistributionMerge with the values known then and checked again at OnInitGlobalModData (after
    the load); if a multiplier changed, the entries are rewritten and the lists parsed again.

    Settings: a bag's stats are worked out when an upgrade goes on or comes off. When the upgrade
    strength options change, the bags carried by each player are re-applied once (checked every ten
    game minutes; nothing is walked while the settings stay the same). The first check after the
    server starts also brings bags left out of step by Dynamic Backpack Upgrades back in line. Bags
    lying in the world are re-applied the next time an upgrade goes on or comes off.
]]

if isClient() then return end

require "Items/ProceduralDistributions"
require "TienBagUpgrades/TienBagUpgrades_Shared"

local TBU = TienBagUpgrades

---------------------------------------------------------------------------------------------------
-- Loot
---------------------------------------------------------------------------------------------------

local ITEMS = {
    Military = { "DynamicBackpacks.UpgradeCapacityMilitary", "DynamicBackpacks.UpgradeWeightReductionMilitary" },
    Leather = { "DynamicBackpacks.UpgradeCapacityLeather", "DynamicBackpacks.UpgradeWeightReductionLeather" },
    Jean = { "DynamicBackpacks.UpgradeCapacityJean", "DynamicBackpacks.UpgradeWeightReductionJean" },
    Cloth = { "DynamicBackpacks.UpgradeCapacityCloth", "DynamicBackpacks.UpgradeWeightReductionCloth" },
}

local ARMY = { "ArmyHangarOutfit", "ArmyStorageOutfit", "LockerArmyBedroom" }
local SURPLUS = { "ArmySurplusBackpacks", "ArmySurplusMisc", "ArmySurplusOutfit" }
local POLICE = { "PoliceStorageOutfit", "PoliceLockers", "SecurityLockers" }
local CAMPING = { "CampingLockers", "CampingStoreBackpacks", "CampingStoreClothes", "CampingStoreGear" }
local GUN_STORE = { "GunStoreCounter", "GunStoreShelf" }
local SAFEHOUSE = { "SafehouseArmor" }
local LEATHER_STORES = { "ClothingStoresJacketsLeather", "ClothingStoresPantsLeather", "CrateLeather", "ClothingStoresSport" }
local JEAN_STORES = { "ClothingStoresJeans", "ClothingStoresOvershirts" }
local CLOTH_STORES = { "ClothingStoresJumpers", "ClothingStoresPants", "ClothingStoresShirts", "ClothingStoresSummer" }
local CLOTHING_STORAGE = { "ClothingStorageAllShirts", "ClothingStorageAllJackets" }
local HOUSE = { "DresserGeneric", "LivingRoomSideTable", "UniversityWardrobe", "BedroomSidetable", "ClosetShelfGeneric",
    "WardrobeGeneric", "WardrobeRedneck", "WardrobeClassy" }
local GARAGE = { "GarageTools", "GarageMetalwork", "GarageCarpentry", "GarageMechanics" }
local GIGAMART = { "GigamartSchool", "GigamartTools" }
local MISC = { "ImprovisedCrafts", "FactoryLockers", "GymLockers", "BarCounterMisc", "CrateTailoring", "CrateClothesRandom" }

-- material -> { { lists, base weight }, ... }  (Dynamic Backpack Upgrades' table)
local LOOT = {
    Military = { { ARMY, 1 }, { POLICE, 1 }, { SURPLUS, 2 }, { CAMPING, 0.6 }, { GUN_STORE, 0.3 }, { GIGAMART, 0.01 },
        { SAFEHOUSE, 0.8 } },
    Leather = { { SAFEHOUSE, 2 }, { LEATHER_STORES, 1 }, { CLOTHING_STORAGE, 0.8 }, { CAMPING, 1.6 }, { POLICE, 4 },
        { MISC, 0.3 }, { GUN_STORE, 1.2 }, { HOUSE, 0.1 }, { GIGAMART, 0.5 }, { GARAGE, 0.5 } },
    Jean = { { SAFEHOUSE, 4 }, { JEAN_STORES, 3 }, { CLOTHING_STORAGE, 1.2 }, { MISC, 1 }, { HOUSE, 0.6 }, { CAMPING, 2 },
        { GARAGE, 1 }, { GIGAMART, 2 } },
    Cloth = { { CLOTH_STORES, 3 }, { CLOTHING_STORAGE, 1.6 }, { HOUSE, 2 }, { CAMPING, 3 }, { MISC, 1 }, { GIGAMART, 3 } },
}

local OUR_ITEMS = {}
for _, items in pairs(ITEMS) do
    for _, fullType in ipairs(items) do OUR_ITEMS[fullType] = true end
end

local lootMultipliers = nil -- material -> multiplier the current entries were written with

local function round2(x)
    return math.floor(x * 100 + 0.5) / 100
end

local function removeOurEntries()
    for _, distribution in pairs(ProceduralDistributions.list) do
        local items = type(distribution) == "table" and distribution.items
        if type(items) == "table" then
            local kept = {}
            for i = 1, #items, 2 do
                if not OUR_ITEMS[items[i]] then
                    kept[#kept + 1] = items[i]
                    kept[#kept + 1] = items[i + 1]
                end
            end
            if #kept ~= #items then
                for i = #items, 1, -1 do items[i] = nil end
                for i = 1, #kept do items[i] = kept[i] end
            end
        end
    end
end

local function writeLoot()
    lootMultipliers = {}
    local missing = {}
    for material, entries in pairs(LOOT) do
        local multiplier = TBU.opt(material .. "LootSpawns")
        lootMultipliers[material] = multiplier
        for _, entry in ipairs(entries) do
            local weight = round2(entry[2] * multiplier)
            if weight > 0 then
                for _, listName in ipairs(entry[1]) do
                    local distribution = ProceduralDistributions.list[listName]
                    if distribution and distribution.items then
                        for _, fullType in ipairs(ITEMS[material]) do
                            table.insert(distribution.items, fullType)
                            table.insert(distribution.items, weight)
                        end
                    else
                        missing[listName] = true
                    end
                end
            end
        end
    end
    for listName in pairs(missing) do
        print("[TienBagUpgrades] loot list not found: " .. listName)
    end
end

local function lootChanged()
    if not lootMultipliers then return true end
    for material in pairs(LOOT) do
        if lootMultipliers[material] ~= TBU.opt(material .. "LootSpawns") then return true end
    end
    return false
end

local function onPreDistributionMerge()
    writeLoot()
end

local function onInitGlobalModData()
    if not lootChanged() then return end
    removeOurEntries()
    writeLoot()
    local ok = pcall(function() IsoWorld.parseDistributions() end)
    if not ok then ItemPickerJava.Parse() end
    print("[TienBagUpgrades] loot weights follow the save's sandbox settings")
end

Events.OnPreDistributionMerge.Add(onPreDistributionMerge)
Events.OnInitGlobalModData.Add(onInitGlobalModData)

---------------------------------------------------------------------------------------------------
-- Stats follow the settings
---------------------------------------------------------------------------------------------------

local checkedPlayers = {} -- player key -> stats signature their bags were checked against

local function refreshBagsIn(container, player)
    local items = container:getItems()
    local changed = 0
    for i = 0, items:size() - 1 do
        local item = items:get(i)
        if item and item:IsInventoryContainer() then
            if TBU.refresh(item, player) then changed = changed + 1 end
            changed = changed + refreshBagsIn(item:getInventory(), player)
        end
    end
    return changed
end

local function checkPlayer(player, key, signature)
    if not player or checkedPlayers[key] == signature then return end
    checkedPlayers[key] = signature
    local changed = refreshBagsIn(player:getInventory(), player)
    if changed > 0 then
        print("[TienBagUpgrades] re-applied " .. changed .. " bag(s) of " .. key)
    end
end

local function everyTenMinutes()
    local signature = TBU.statsSignature()
    if isServer() then
        local players = getOnlinePlayers()
        for i = 0, players:size() - 1 do
            local player = players:get(i)
            checkPlayer(player, player:getUsername(), signature)
        end
    else
        for i = 0, getNumActivePlayers() - 1 do
            checkPlayer(getSpecificPlayer(i), "local" .. i, signature)
        end
    end
end

Events.EveryTenMinutes.Add(everyTenMinutes)
