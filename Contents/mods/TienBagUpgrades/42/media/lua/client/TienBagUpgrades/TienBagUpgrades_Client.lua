--[[
    Tien's Bag Upgrades - context menus and the server's stats messages.

    Right-click a bag: Add Upgrade (one entry per upgrade type the player carries) and Remove Upgrade.
    Right-click an upgrade item: Sew onto Bag (every container item in the inventory, worn ones and
    ones inside other bags included).
    The options queue transfers into the main inventory for whatever is elsewhere, then the timed
    action, which makes the change on the server.

    Menus only read the bags; nothing here writes their modData or stats except "bagStats", the
    server's answer after it changed a bag this player owns.
]]

require "TienBagUpgrades/TienBagUpgrades_Shared"
require "TimedActions/TienBagAddUpgradeAction"
require "TimedActions/TienBagRemoveUpgradeAction"

local TBU = TienBagUpgrades

local function fmtInt(n)
    return string.format("%d", n)
end

local function fmtWeight(n)
    return string.format("%.1f", n)
end

local function disable(option, text)
    option.notAvailable = true
    local tooltip = ISInventoryPaneContextMenu.addToolTip()
    tooltip.description = text
    option.toolTip = tooltip
end

local function describe(option, text)
    local tooltip = ISInventoryPaneContextMenu.addToolTip()
    tooltip.description = text
    option.toolTip = tooltip
end

local function firstItem(items)
    local entry = items[1]
    if not entry then return nil end
    if instanceof(entry, "InventoryItem") then return entry end
    return entry.items and entry.items[1] or nil
end

-- One entry per upgrade type the player carries anywhere in the inventory: { type, item, count }.
local function carriedUpgrades(inventory)
    local found = {}
    for _, upgradeType in ipairs(TBU.UPGRADE_ORDER) do
        local fullType = TBU.fullType(upgradeType)
        local item = inventory:getFirstTypeRecurse(fullType)
        if item then
            found[#found + 1] = { type = upgradeType, item = item, count = inventory:getCountTypeRecurse(fullType) }
        end
    end
    return found
end

local function cutterMissingText()
    if TBU.opt("KnivesCanRemove") then return getText("Tooltip_TienBagUpgrades_NeedCutterOrKnife") end
    return getText("Tooltip_TienBagUpgrades_NeedCutter")
end

---------------------------------------------------------------------------------------------------
-- Actions
---------------------------------------------------------------------------------------------------

local function onAddUpgrade(player, bag, upgrade)
    local inventory = player:getInventory()
    local needle, thread = TBU.findNeedle(inventory), TBU.findThread(inventory)
    if not needle or not thread then return end
    ISInventoryPaneContextMenu.transferIfNeeded(player, bag)
    ISInventoryPaneContextMenu.transferIfNeeded(player, upgrade)
    ISInventoryPaneContextMenu.transferIfNeeded(player, needle)
    ISInventoryPaneContextMenu.transferIfNeeded(player, thread)
    ISTimedActionQueue.add(TienBagAddUpgradeAction:new(player, bag, upgrade, needle, thread))
end

local function onRemoveUpgrade(player, bag, upgradeType)
    local cutter = TBU.findCutter(player:getInventory())
    if not cutter then return end
    ISInventoryPaneContextMenu.transferIfNeeded(player, bag)
    ISInventoryPaneContextMenu.transferIfNeeded(player, cutter)
    ISTimedActionQueue.add(TienBagRemoveUpgradeAction:new(player, bag, upgradeType, cutter))
end

---------------------------------------------------------------------------------------------------
-- Menus
---------------------------------------------------------------------------------------------------

local function addBagOptions(player, context, bag)
    local inventory = player:getInventory()
    local used = TBU.countUpgrades(bag)
    local max = TBU.maxSlots(bag, player)

    local carried = max > 0 and carriedUpgrades(inventory) or {}
    if #carried > 0 then
        local option = context:addOption(getText("ContextMenu_TienBagUpgrades_AddUpgrade"))
        if used >= max then
            disable(option, getText("Tooltip_TienBagUpgrades_NoFreeSlot", fmtInt(used), fmtInt(max)))
        elseif not TBU.findNeedle(inventory) or not TBU.findThread(inventory) then
            disable(option, getText("Tooltip_TienBagUpgrades_NeedNeedleThread"))
        else
            local sub = ISContextMenu:getNew(context)
            context:addSubMenu(option, sub)
            for _, entry in ipairs(carried) do
                local name = entry.item:getDisplayName()
                if entry.count > 1 then name = name .. " (" .. fmtInt(entry.count) .. ")" end
                local subOption = sub:addOption(name, player, onAddUpgrade, bag, entry.item)
                subOption.itemForTexture = entry.item
                describe(subOption, TBU.describeUpgrade(entry.type))
            end
        end
    end

    local upgrades = TBU.getUpgrades(bag)
    if upgrades then
        local option = context:addOption(getText("ContextMenu_TienBagUpgrades_RemoveUpgrade"))
        if not TBU.findCutter(inventory) then
            disable(option, cutterMissingText())
        else
            local sub = ISContextMenu:getNew(context)
            context:addSubMenu(option, sub)
            local counts, order = {}, {}
            for _, upgradeType in ipairs(upgrades) do
                if not counts[upgradeType] then order[#order + 1] = upgradeType end
                counts[upgradeType] = (counts[upgradeType] or 0) + 1
            end
            for _, upgradeType in ipairs(order) do
                local name = TBU.upgradeName(upgradeType)
                if counts[upgradeType] > 1 then name = name .. " (" .. fmtInt(counts[upgradeType]) .. ")" end
                local subOption = sub:addOption(name, player, onRemoveUpgrade, bag, upgradeType)
                local ok, weight, capacity = TBU.removeCheck(bag, upgradeType)
                if not ok then
                    disable(subOption, getText("Tooltip_TienBagUpgrades_TooFull", fmtWeight(weight), fmtInt(capacity)))
                end
            end
        end
    end
end

local function addUpgradeItemOptions(player, context, upgrade)
    local inventory = player:getInventory()
    local bags = {}
    -- Containers anywhere in the inventory, inside other bags too; onAddUpgrade brings them out first.
    local items = inventory:getAllEvalRecurse(function(item)
        return TBU.isBag(item) and TBU.maxSlots(item, player) > 0
    end, ArrayList.new())
    for i = 0, items:size() - 1 do
        bags[#bags + 1] = items:get(i)
    end
    if #bags == 0 then return end

    local option = context:addOption(getText("ContextMenu_TienBagUpgrades_SewOnto"))
    describe(option, TBU.describeUpgrade(upgrade:getType()))
    if not TBU.findNeedle(inventory) or not TBU.findThread(inventory) then
        disable(option, getText("Tooltip_TienBagUpgrades_NeedNeedleThread"))
        return
    end
    local sub = ISContextMenu:getNew(context)
    context:addSubMenu(option, sub)
    for _, bag in ipairs(bags) do
        local used, max = TBU.countUpgrades(bag), TBU.maxSlots(bag, player)
        local name = bag:getDisplayName() .. " (" .. fmtInt(used) .. "/" .. fmtInt(max) .. ")"
        local subOption = sub:addOption(name, player, onAddUpgrade, bag, upgrade)
        subOption.itemForTexture = bag
        if used >= max then
            disable(subOption, getText("Tooltip_TienBagUpgrades_NoFreeSlot", fmtInt(used), fmtInt(max)))
        end
    end
end

local function onFillInventoryObjectContextMenu(playerNum, context, items)
    local player = getSpecificPlayer(playerNum)
    local item = firstItem(items)
    if not player or not item then return end
    if TBU.isBag(item) then
        addBagOptions(player, context, item)
    elseif TBU.upgradeInfo(item) then
        addUpgradeItemOptions(player, context, item)
    end
end

Events.OnFillInventoryObjectContextMenu.Add(onFillInventoryObjectContextMenu)

---------------------------------------------------------------------------------------------------
-- Server messages
---------------------------------------------------------------------------------------------------

-- The server changed one of this client's bags; the item sync does not carry capacity or weight
-- reduction, so write them (and the upgrade list) on the client's copy.
local function onBagStats(args)
    if type(args.id) ~= "number" then return end
    for i = 0, getNumActivePlayers() - 1 do
        local player = getSpecificPlayer(i)
        local bag = player and player:getInventory():getItemById(args.id)
        if bag and bag:IsInventoryContainer() then
            local md = bag:getModData()
            local list = {}
            if type(args.upgrades) == "table" then
                for n = 1, #args.upgrades do list[n] = args.upgrades[n] end
            end
            md.LUpgrades = list
            md.LCapacity = args.baseCapacity
            md.LWeightReduction = args.baseWeightReduction
            md.LMaxUpgrades = TBU.baseSlots(bag)
            if md.LFixState == nil then md.LFixState = "Show" end
            md.LDynamicBackpacksInit = true
            TBU.setStats(bag, args.capacity, args.weightReduction)
            ISInventoryPage.renderDirty = true
            return
        end
    end
end

local function onServerCommand(module, command, args)
    if module ~= TBU.MODULE or type(args) ~= "table" then return end
    if command == TBU.CMD_BAG_STATS then onBagStats(args) end
end

Events.OnServerCommand.Add(onServerCommand)
