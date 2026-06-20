'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';

export interface SearchFilters {
  colors: string[];
  colorMatch: string;
  commanderIdentity: string[];
  type: string;
  rarity: string[];
  text: string;
  quantityOperator: string;
  quantity: string;
  mana_costOperator: string;
  mana_cost: string;
  powerOperator: string;
  power: string;
  toughnessOperator: string;
  toughness: string;
}

interface SearchSidebarProps {
  onSearch: (filters: SearchFilters) => void;
  onClear?: () => void;
  isLoading?: boolean;
}

const COLORS = ['White', 'Blue', 'Black', 'Red', 'Green', 'Colorless'];
const COMMANDER_IDENTITY = ['White', 'Blue', 'Black', 'Red', 'Green', 'Colorless'];
const RARITIES = ['Common', 'Uncommon', 'Rare', 'Mythic'];

export function SearchSidebar({ onSearch, onClear, isLoading = false }: SearchSidebarProps) {
  const [filters, setFilters] = useState<SearchFilters>({
    colors: [],
    colorMatch: 'exact',
    commanderIdentity: [],
    type: '',
    rarity: [],
    text: '',
    quantityOperator: '>=',
    quantity: '',
    mana_costOperator: '=',
    mana_cost: '',
    powerOperator: '=',
    power: '',
    toughnessOperator: '=',
    toughness: '',
  });

  const toggleColor = (color: string) => {
    setFilters((prev) => ({
      ...prev,
      colors: prev.colors.includes(color)
        ? prev.colors.filter((c) => c !== color)
        : [...prev.colors, color],
    }));
  };

  const toggleCommanderIdentity = (color: string) => {
    setFilters((prev) => ({
      ...prev,
      commanderIdentity: prev.commanderIdentity.includes(color)
        ? prev.commanderIdentity.filter((c) => c !== color)
        : [...prev.commanderIdentity, color],
    }));
  };

  const handleClear = () => {
    setFilters({
      colors: [], colorMatch: 'exact', commanderIdentity: [], type: '', rarity: [], text: '',
      quantityOperator: '>=', quantity: '', mana_costOperator: '=', mana_cost: '',
      powerOperator: '=', power: '', toughnessOperator: '=', toughness: '',
    });
    if (onClear) onClear();
  };

  const handleSearch = () => {
    onSearch(filters);
  };

  return (
    <aside className="w-64 bg-card border-r border-border p-6 overflow-y-auto max-h-screen">
      <div className="space-y-6">
        <div className="space-y-2">
          <Button
            onClick={handleSearch}
            disabled={isLoading}
            className="w-full bg-indigo-600 text-white hover:bg-indigo-700"
          >
            {isLoading ? 'Searching...' : 'Search'}
          </Button>
          <Button
            onClick={handleClear}
            disabled={isLoading}
            variant="outline"
            className="w-full border-border hover:bg-muted text-foreground"
          >
            Clear Search
          </Button>
        </div>

        {/* Quantity Owned */}
        <div className="space-y-2">
          <Label htmlFor="quantity" className="text-sm font-semibold">
            Quantity Owned
          </Label>
          <div className="flex gap-2">
            <select
              className="flex h-9 w-16 rounded-md border border-input bg-background px-2 py-1 text-sm text-foreground shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              value={filters.quantityOperator}
              onChange={(e) => setFilters(prev => ({ ...prev, quantityOperator: e.target.value }))}
            >
              <option value=">=">&ge;</option>
              <option value=">">&gt;</option>
              <option value="=">=</option>
              <option value="<=">&le;</option>
              <option value="<">&lt;</option>
            </select>
            <Input
              id="quantity"
              type="number"
              min="0"
              placeholder="Amount"
              value={filters.quantity}
              onChange={(e) => {
                const val = e.target.value;
                if (val !== '' && parseInt(val) < 0) return;
                setFilters(prev => ({ ...prev, quantity: val }));
              }}
              className="bg-background border-border text-foreground flex-1"
            />
          </div>
        </div>

        {/* Colors */}
        <div className="space-y-3">
          <h3 className="font-semibold text-foreground text-sm">Colors</h3>
          <div className="space-y-2">
            {COLORS.map((color) => (
              <div key={color} className="flex items-center space-x-2">
                <Checkbox
                  id={`color-${color}`}
                  checked={filters.colors.includes(color)}
                  onCheckedChange={() => toggleColor(color)}
                />
                <Label htmlFor={`color-${color}`} className="text-sm font-normal cursor-pointer">
                  {color}
                </Label>
              </div>
            ))}
            <select
              className="mt-2 flex w-full h-9 rounded-md border border-input bg-background px-3 py-1 text-sm text-foreground shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              value={filters.colorMatch}
              onChange={(e) => setFilters(prev => ({ ...prev, colorMatch: e.target.value }))}
            >
              <option value="including">Including these colors</option>
              <option value="exact">Exactly these colors</option>
            </select>
          </div>
        </div>

        {/* Commander Identity */}
        <div className="space-y-3">
          <h3 className="font-semibold text-foreground text-sm">Commander Identity</h3>
          <div className="space-y-2">
            {COMMANDER_IDENTITY.map((color) => (
              <div key={color} className="flex items-center space-x-2">
                <Checkbox
                  id={`commander-${color}`}
                  checked={filters.commanderIdentity.includes(color)}
                  onCheckedChange={() => toggleCommanderIdentity(color)}
                />
                <Label htmlFor={`commander-${color}`} className="text-sm font-normal cursor-pointer">
                  {color}
                </Label>
              </div>
            ))}
          </div>
        </div>

        {/* Type */}
        <div className="space-y-2">
          <Label htmlFor="type" className="text-sm font-semibold">Type</Label>
          <Input
            id="type"
            placeholder="e.g., Legendary Creature"
            value={filters.type}
            onChange={(e) => setFilters((prev) => ({ ...prev, type: e.target.value }))}
            className="bg-background border-border text-foreground"
          />
        </div>

        {/* CMC */}
        <div className="space-y-2">
          <Label htmlFor="mana_cost" className="text-sm font-semibold">CMC</Label>
          <div className="flex gap-2">
            <select
              className="flex h-9 w-16 rounded-md border border-input bg-background px-2 py-1 text-sm text-foreground shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              value={filters.mana_costOperator}
              onChange={(e) => setFilters(prev => ({ ...prev, mana_costOperator: e.target.value }))}
            >
              <option value="=">=</option>
              <option value=">=">&ge;</option>
              <option value=">">&gt;</option>
              <option value="<=">&le;</option>
              <option value="<">&lt;</option>
            </select>
            <Input
              id="mana_cost"
              type="number"
              min="0"
              placeholder="0"
              value={filters.mana_cost}
              onChange={(e) => {
                const val = e.target.value;
                if (val !== '' && parseInt(val) < 0) return;
                setFilters(prev => ({ ...prev, mana_cost: val }));
              }}
              className="bg-background border-border text-foreground flex-1"
            />
          </div>
        </div>

        {/* Rarity */}
        <div className="space-y-3">
          <h3 className="font-semibold text-foreground text-sm">Rarity</h3>
          <RadioGroup
            value={filters.rarity[0] || 'any'}
            onValueChange={(value) =>
              setFilters((prev) => ({ ...prev, rarity: value === 'any' ? [] : [value] }))
            }
          >
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="any" id="rarity-any" />
              <Label htmlFor="rarity-any" className="text-sm font-normal cursor-pointer text-muted-foreground">
                Any / Clear
              </Label>
            </div>
            {RARITIES.map((rarity) => (
              <div key={rarity} className="flex items-center space-x-2">
                <RadioGroupItem value={rarity.toLowerCase()} id={`rarity-${rarity}`} />
                <Label htmlFor={`rarity-${rarity}`} className="text-sm font-normal cursor-pointer">
                  {rarity}
                </Label>
              </div>
            ))}
          </RadioGroup>
        </div>

        {/* Text/Ability */}
        <div className="space-y-2">
          <Label htmlFor="text" className="text-sm font-semibold">Text/Ability</Label>
          <Textarea
            id="text"
            placeholder="Search card abilities..."
            value={filters.text}
            onChange={(e) => setFilters((prev) => ({ ...prev, text: e.target.value }))}
            className="bg-background border-border text-foreground min-h-24 resize-none"
          />
        </div>

        {/* Power */}
        <div className="space-y-2">
          <Label htmlFor="power" className="text-sm font-semibold">Power</Label>
          <div className="flex gap-2">
            <select
              className="flex h-9 w-16 rounded-md border border-input bg-background px-2 py-1 text-sm text-foreground shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              value={filters.powerOperator}
              onChange={(e) => setFilters(prev => ({ ...prev, powerOperator: e.target.value }))}
            >
              <option value="=">=</option>
              <option value=">=">&ge;</option>
              <option value=">">&gt;</option>
              <option value="<=">&le;</option>
              <option value="<">&lt;</option>
            </select>
            <Input
              id="power"
              type="number"
              placeholder="0"
              value={filters.power}
              onChange={(e) => setFilters(prev => ({ ...prev, power: e.target.value }))}
              className="bg-background border-border text-foreground flex-1"
            />
          </div>
        </div>

        {/* Toughness */}
        <div className="space-y-2">
          <Label htmlFor="toughness" className="text-sm font-semibold">Toughness</Label>
          <div className="flex gap-2">
            <select
              className="flex h-9 w-16 rounded-md border border-input bg-background px-2 py-1 text-sm text-foreground shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              value={filters.toughnessOperator}
              onChange={(e) => setFilters(prev => ({ ...prev, toughnessOperator: e.target.value }))}
            >
              <option value="=">=</option>
              <option value=">=">&ge;</option>
              <option value=">">&gt;</option>
              <option value="<=">&le;</option>
              <option value="<">&lt;</option>
            </select>
            <Input
              id="toughness"
              type="number"
              placeholder="0"
              value={filters.toughness}
              onChange={(e) => setFilters(prev => ({ ...prev, toughness: e.target.value }))}
              className="bg-background border-border text-foreground flex-1"
            />
          </div>
        </div>
      </div>
    </aside>
  );
}