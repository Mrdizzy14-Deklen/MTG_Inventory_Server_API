'use client';

import { useEffect, useState, useMemo } from 'react';
import Link from 'next/link';
import Cookies from 'js-cookie';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { SearchSidebar, SearchFilters as SidebarFilters } from '@/components/SearchSidebar';
import { CardGrid } from '@/components/CardGrid';
import { CardDetailModal } from '@/components/CardDetailModal';
import { fetchInventory, fetchCards, updatePreference, removePreference, fetchPreferences, Card } from '@/lib/mtg-client';
import { useRouter } from 'next/navigation';

export default function Page() {
  const router = useRouter(); 
  
  const [cards, setCards] = useState<Card[]>([]);
  const [cardName, setCardName] = useState('');
  const [preferences, setPreferences] = useState<Record<string, any>>({});
  const [showUnowned, setShowUnowned] = useState(false);
  const [selectedCard, setSelectedCard] = useState<Card | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSearching, setIsSearching] = useState(false);
  const [sortBy, setSortBy] = useState('name');
  const [sortOrder, setSortOrder] = useState('asc');

  const sortedCards = useMemo(() => {
    const cardsCopy = [...cards];
    cardsCopy.sort((a, b) => {
      const nameA = a.card_name || a.name || '';
      const nameB = b.card_name || b.name || '';

      let result = 0;

      if (sortBy === 'cmc') {
        const cmcA = a.mana_cost || 0;
        const cmcB = b.mana_cost || 0;
        if (cmcA !== cmcB) {
          result = cmcA - cmcB;
        } else {
          result = nameA.localeCompare(nameB);
        }
      }else if (sortBy === 'color') {
        const getColorData = (card: any) => {
          const w = card.w ? 1 : 0;
          const u = card.u ? 1 : 0;
          const b = card.b ? 1 : 0;
          const r = card.r ? 1 : 0;
          const g = card.g ? 1 : 0;

          const colorCount = w + u + b + r + g;
          
          const group = colorCount === 0 ? 6 : colorCount;
          
          const binaryScore = (w * 16) + (u * 8) + (b * 4) + (r * 2) + (g * 1);
          
          return { group, binaryScore };
        };

        const dataA = getColorData(a);
        const dataB = getColorData(b);

        if (dataA.group !== dataB.group) {
          result = dataA.group - dataB.group;
        } else if (dataA.binaryScore !== dataB.binaryScore) {
          result = dataB.binaryScore - dataA.binaryScore;
        } else {
          result = nameA.localeCompare(nameB);
        }
      }else{
        result = nameA.localeCompare(nameB);
      }

      return sortOrder === 'desc' ? result * -1 : result;
    });
    
    return cardsCopy;
  }, [cards, sortBy, sortOrder]);

  useEffect(() => {
    const loadInitialData = async () => {
      try {
        const [inventory, userPrefs] = await Promise.all([
          fetchInventory(),
          fetchPreferences()
        ]);
        
        setCards(inventory);

        const prefMap: Record<string, any> = {};
        if (userPrefs && Array.isArray(userPrefs)) {
          userPrefs.forEach((pref: any) => {
            prefMap[pref.oracle_id] = pref;
          });
        }
        setPreferences(prefMap);

      } catch (error: any) {
        console.error('Failed to load data:', error);
        if (error.message && error.message.includes('401')) {
          Cookies.remove('authToken');
          router.push('/login');
        }
      } finally {
        setIsLoading(false);
      }
    };

    loadInitialData();
  }, [router]);

  const emptySidebarFilters: SidebarFilters = {
    colors: [], colorMatch: 'exact', commanderIdentity: [], type: '', cmc: '', rarity: [], text: '', power: '', toughness: '', quantityOperator: '>=', quantityValue: ''
  };

  const handleSearch = async (sidebarFilters: SidebarFilters = emptySidebarFilters) => {
    setIsSearching(true);
    try {
      const apiFilters: any = {};

      let currentShowUnowned = showUnowned;

      if (sidebarFilters.quantityValue !== '') {
        const qVal = parseInt(sidebarFilters.quantityValue, 10);
        const qOp = sidebarFilters.quantityOperator;
        
        if ((qOp === '>' && qVal >= 0) || (qOp === '>=' && qVal >= 1) || (qOp === '=' && qVal >= 1)) {
          setShowUnowned(false);
          currentShowUnowned = false;
        }

        apiFilters.quantity_operator = qOp;
        apiFilters.quantity_value = qVal;
      }

      const colorMap: Record<string, string> = {
        'White': 'W',
        'Blue': 'U',
        'Black': 'B',
        'Red': 'R',
        'Green': 'G',
        'Colorless': 'C'
      };

      if (cardName) apiFilters.card_name = cardName;

      if (sidebarFilters.colors && sidebarFilters.colors.length > 0) {
        const mappedColors = sidebarFilters.colors.map(c => colorMap[c]);
        const isExact = sidebarFilters.colorMatch === 'exact';
        const includesColorless = mappedColors.includes('C');

        const enforceFalse = isExact || includesColorless;
        
        if (mappedColors.includes('W')) apiFilters.w = true; else if (enforceFalse) apiFilters.w = false;
        if (mappedColors.includes('U')) apiFilters.u = true; else if (enforceFalse) apiFilters.u = false;
        if (mappedColors.includes('B')) apiFilters.b = true; else if (enforceFalse) apiFilters.b = false;
        if (mappedColors.includes('R')) apiFilters.r = true; else if (enforceFalse) apiFilters.r = false;
        if (mappedColors.includes('G')) apiFilters.g = true; else if (enforceFalse) apiFilters.g = false;
      }

      if (sidebarFilters.commanderIdentity && sidebarFilters.commanderIdentity.length > 0) {
        apiFilters.commander_identity = sidebarFilters.commanderIdentity.map(c => colorMap[c]);
      }

      if (sidebarFilters.type) apiFilters.type_line = sidebarFilters.type;
      
      if (sidebarFilters.cmc) {
        const parsedCmc = parseInt(sidebarFilters.cmc);
        if (!isNaN(parsedCmc)) {
          apiFilters.mana_cost = parsedCmc;
        }
      }

      if (sidebarFilters.rarity && sidebarFilters.rarity.length > 0) {
        apiFilters.rarity = sidebarFilters.rarity[0];
      }
      
      if (sidebarFilters.text) apiFilters.text_box = sidebarFilters.text;
      if (sidebarFilters.power) apiFilters.power = sidebarFilters.power;
      if (sidebarFilters.toughness) apiFilters.toughness = sidebarFilters.toughness;

      if (!currentShowUnowned) apiFilters.owned = true;

      const results = await fetchCards(apiFilters);
      setCards(results);
    } catch (error: any) {
      console.error('Search failed:', error);
      if (error.message && error.message.includes('401')) {
        Cookies.remove('authToken');
        router.push('/login');
      }
    } finally {
      setIsSearching(false);
    }
  };

  const handleCardClick = (card: Card) => {
    setSelectedCard(card);
    setIsDetailModalOpen(true);
  };

  const handleUpdatePreference = async (oracleId: string, preference: string, title: string, notes: string) => {
    try {

      const enumMap: Record<string, string> = {
        'For Trade': 'for_trade',
        'Looking For': 'looking_for',
        'Not For Trade': 'not_for_trade'
      };

      await updatePreference({
        oracle_id: oracleId,
        status: enumMap[preference],
        tag: title || undefined,
        notes: notes || undefined,
      });

    } catch (error) {
      console.error('Failed to update preference:', error);
      throw error;
    }
  };

  return (
    <div className="flex h-screen bg-background">
      <SearchSidebar onSearch={handleSearch} isLoading={isSearching} />

      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="border-b border-border p-6 bg-card space-y-4">
          <div className="flex items-center gap-4">
            <Input
              placeholder="Search by card name... (Press Enter)"
              value={cardName}
              onChange={(e) => setCardName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSearch(emptySidebarFilters);
              }}
              className="flex-1 bg-background border-border text-foreground"
            />
            <Button 
              onClick={() => handleSearch(emptySidebarFilters)}
              className="bg-indigo-600 hover:bg-indigo-700 text-white"
            >
              Search
            </Button>
            <Link href="/bulk-manage">
              <Button variant="outline" className="border-border hover:bg-muted text-foreground">
                Add/Remove Cards
              </Button>
            </Link>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Checkbox
                id="show-unowned"
                checked={showUnowned}
                onCheckedChange={(checked) => setShowUnowned(checked as boolean)}
              />
              <Label htmlFor="show-unowned" className="cursor-pointer text-sm">
                Show cards I don&apos;t own
              </Label>
            </div>

            <div className="flex items-center space-x-2">
              <Label htmlFor="sort-by" className="text-sm font-medium text-foreground">
                Sort by:
              </Label>
              <select
                id="sort-by"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="flex h-9 rounded-md border border-input bg-background px-3 py-1 text-sm text-foreground shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="name">Name</option>
                <option value="color">Color</option>
                <option value="cmc">CMC</option>
              </select>
              <select
                id="sort-order"
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value)}
                className="flex h-9 rounded-md border border-input bg-background px-3 py-1 text-sm text-foreground shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="asc">Ascending</option>
                <option value="desc">Descending</option>
              </select>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          <CardGrid
            cards={sortedCards}
            preferences={preferences}
            showUnowned={showUnowned}
            onCardClick={handleCardClick}
            isLoading={isLoading || isSearching}
          />
        </div>
      </div>

      {selectedCard && (
        <CardDetailModal
          card={selectedCard}
          isOpen={isDetailModalOpen}
          onClose={() => {
            setIsDetailModalOpen(false);
            setSelectedCard(null);
          }}
          onUpdatePreference={handleUpdatePreference}
        />
      )}
    </div>
  );
}