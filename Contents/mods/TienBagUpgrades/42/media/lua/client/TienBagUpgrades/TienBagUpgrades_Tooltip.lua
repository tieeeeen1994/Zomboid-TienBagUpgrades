--[[
    Tien's Bag Upgrades - extra lines in item tooltips.

    Bags: upgrade slots used / available, and what the upgrades add to capacity and weight reduction.
    Upgrade items: what they do with the current sandbox settings.

    The lines go under the finished tooltip, after the whole render chain (vanilla's and every other
    mod's) has drawn it: the box is extended down, its bottom border painted over, the border drawn again
    around the whole, the lines drawn in. No method of the tooltip is swapped during the render, so
    another mod's calls in the middle of it (Plysken Attachments Reborn calls setHeight and
    drawRectBorder for its own box) are never mistaken for vanilla's.

    Then the ObjectTooltip's height is set to the extended box. Plysken Attachments Reborn draws a bag's
    attachment slots in a box of its own under the tooltip, at the ObjectTooltip's height as the next
    frame begins (zPAR_Tooltip.lua injectTooltip); with this it starts under these lines instead of on
    top of them, whichever of the two mods loads first. Vanilla measures the ObjectTooltip again every
    frame, so nothing else sees the change.

    The lines are built once and reused while the item and its numbers stay the same; nothing is written
    to the item.
]]

require "ISUI/ISToolTipInv"
require "TienBagUpgrades/TienBagUpgrades_Shared"

local TBU = TienBagUpgrades

local LINE_R, LINE_G, LINE_B = 0.68, 0.64, 0.96

local cache = { item = nil }

local function fmtInt(n)
    return string.format("%d", n)
end

local function bagLines(bag, used, max, capacity, reduction)
    local lines = {}
    if max > 0 or used > 0 then
        lines[#lines + 1] = getText("IGUI_TienBagUpgrades_Slots", fmtInt(used), fmtInt(math.max(max, used)))
    end
    if used > 0 then
        local baseCapacity, baseReduction = TBU.baseStats(bag)
        local _, _, uncapped = TBU.targetStats(bag)
        local addedCapacity = capacity - baseCapacity
        if uncapped > capacity then
            lines[#lines + 1] = getText("IGUI_TienBagUpgrades_CapacityCapped", fmtInt(addedCapacity), fmtInt(capacity))
        elseif addedCapacity ~= 0 then
            lines[#lines + 1] = getText("IGUI_TienBagUpgrades_Capacity", fmtInt(addedCapacity))
        end
        local addedReduction = reduction - baseReduction
        if addedReduction ~= 0 then
            lines[#lines + 1] = getText("IGUI_TienBagUpgrades_WeightReduction", fmtInt(addedReduction))
        end
    end
    if #lines == 0 then return nil end
    return lines
end

local function linesFor(item)
    if not item or not instanceof(item, "InventoryItem") then return nil end
    if TBU.isBag(item) then
        local used, max = TBU.countUpgrades(item), TBU.maxSlots(item, getPlayer())
        local capacity, reduction = item:getCapacity(), item:getWeightReduction()
        if cache.item == item and cache.used == used and cache.max == max
            and cache.capacity == capacity and cache.reduction == reduction then
            return cache.lines
        end
        cache.item, cache.used, cache.max, cache.capacity, cache.reduction = item, used, max, capacity, reduction
        cache.lines = bagLines(item, used, max, capacity, reduction)
        return cache.lines
    end
    local info = TBU.upgradeInfo(item)
    if not info then return nil end
    if cache.item ~= item then
        cache.item, cache.used, cache.max = item, nil, nil
        cache.lines = { TBU.describeUpgrade(item:getType()) }
    end
    return cache.lines
end

local originalRender = ISToolTipInv.render

function ISToolTipInv:render()
    local lines = linesFor(self.item)
    originalRender(self)
    if not lines then return end
    -- Vanilla draws nothing while a context menu is open.
    if ISContextMenu.instance and ISContextMenu.instance.visibleCheck then return end
    local tooltip = self.tooltip
    if not tooltip then return end

    local spacing = tooltip:getLineSpacing()
    local top = self.height
    local extra = math.floor((#lines + 0.5) * spacing)
    local bg, border = self.backgroundColor, self.borderColor
    -- Over the old bottom border row too, then the border again around the taller box.
    self:drawRect(0, top - 1, self.width, extra + 1, bg.a, bg.r, bg.g, bg.b)
    self:setHeight(top + extra)
    self:drawRectBorder(0, 0, self.width, self.height, border.a, border.r, border.g, border.b)
    local font = UIFont[getCore():getOptionTooltipFont()]
    for i = 1, #lines do
        tooltip:DrawText(font, lines[i], 5, top + spacing * (i - 1), LINE_R, LINE_G, LINE_B, 1)
    end
    tooltip:setHeight(self.height)
end

-- Sandbox values can change during a game; rebuild the lines now and then.
Events.EveryTenMinutes.Add(function()
    cache.item = nil
end)
