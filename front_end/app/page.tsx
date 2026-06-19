'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import Cookies from 'js-cookie';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { SearchSidebar, SearchFilters as SidebarFilters } from '@/components/SearchSidebar';
import { CardGrid } from '@/components/CardGrid';
import { CardDetailModal } from '@/components/CardDetailModal';
import { fetchInventory, fetchCards, updatePreference, removePreference, Card } from '@/lib/mtg-client';
import { useRouter } from 'next/navigation';

export default function Page() {
  const router = useRouter(); 
  
  const [cards, setCards] = useState<Card[]>([]);
  const [cardName, setCardName] = useState('');
  const [showUnowned, setShowUnowned] = useState(false);
  const [selectedCard, setSelectedCard] = useState<Card | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSearching, setIsSearching] = useState(false);

  useEffect(() => {
    const loadInventory = async () => {
      try {
        const inventory = await fetchInventory();
        setCards(inventory);
      } catch (error: any) {
        console.error('Failed to load inventory:', error);
        if (error.message && error.message.includes('401')) {
          Cookies.remove('authToken');
          router.push('/login');
        }
      } finally {
        setIsLoading(false);
      }
    };

    loadInventory();
  }, [router]);

  const emptySidebarFilters: SidebarFilters = {
    colors: [], commanderIdentity: [], type: '', cmc: '', rarity: '', text: '', power: '', toughness: ''
  };

  const handleSearch = async (sidebarFilters: SidebarFilters = emptySidebarFilters) => {
    setIsSearching(true);
    try {
      const apiFilters: any = {};

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
        
        if (mappedColors.includes('W')) apiFilters.w = true;
        if (mappedColors.includes('U')) apiFilters.u = true;
        if (mappedColors.includes('B')) apiFilters.b = true;
        if (mappedColors.includes('R')) apiFilters.r = true;
        if (mappedColors.includes('G')) apiFilters.g = true;
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

      if (!showUnowned) apiFilters.owned = true;

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

          <div className="flex items-center space-x-2">
            <Checkbox
              id="show-unowned"
              checked={showUnowned}
              onCheckedChange={(checked) => setShowUnowned(checked as boolean)}
            />
            <Label htmlFor="show-unowned" className="cursor-pointer text-sm">
              Show global database (cards I don&apos;t own)
            </Label>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          <CardGrid
            cards={cards}
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