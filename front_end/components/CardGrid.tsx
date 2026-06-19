'use client';

import { useState, useEffect, useRef } from 'react';
import Image from 'next/image';
import { Card } from '@/lib/mtg-client';
import { Button } from '@/components/ui/button';
import { ChevronLeft, ChevronRight } from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://vm.deklenn.dev';

interface CardGridProps {
  cards: Card[];
  preferences?: Record<string, any>;
  showUnowned: boolean;
  onCardClick: (card: Card) => void;
  isLoading?: boolean;
}

export function CardGrid({
  cards,
  preferences = {},
  showUnowned,
  onCardClick,
  isLoading = false,
}: CardGridProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const gridTopRef = useRef<HTMLDivElement>(null);
  
  const CARDS_PER_PAGE = 60;

  useEffect(() => {
    setCurrentPage(1);
  }, [cards, showUnowned]);

  const filteredCards = showUnowned 
    ? cards 
    : cards.filter((card) => card.quantity > 0);

  const totalCards = filteredCards.length;
  const totalPages = Math.ceil(totalCards / CARDS_PER_PAGE);
  const startIndex = (currentPage - 1) * CARDS_PER_PAGE;
  const endIndex = Math.min(startIndex + CARDS_PER_PAGE, totalCards);
  
  const visibleCards = filteredCards.slice(startIndex, endIndex);

  const handlePageChange = (newPage: number) => {
    setCurrentPage(newPage);
    gridTopRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="text-muted-foreground animate-pulse">Loading cards...</span>
      </div>
    );
  }

  if (totalCards === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="text-muted-foreground">No cards found</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full" ref={gridTopRef}>
      <div className="flex justify-between items-center mb-6 text-sm text-zinc-400">
        <p>
          <strong className="text-zinc-100">{startIndex + 1} – {endIndex}</strong> of <strong className="text-zinc-100">{totalCards.toLocaleString()}</strong> cards
        </p>
        
        {/* Top Mini Controls */}
        {totalPages > 1 && (
          <div className="flex space-x-2">
            <Button 
              variant="outline" 
              size="icon"
              className="h-8 w-8"
              onClick={() => handlePageChange(Math.max(currentPage - 1, 1))}
              disabled={currentPage === 1}
            >
              <ChevronLeft className="w-4 h-4" />
            </Button>
            <Button 
              variant="outline" 
              size="icon"
              className="h-8 w-8"
              onClick={() => handlePageChange(Math.min(currentPage + 1, totalPages))}
              disabled={currentPage === totalPages}
            >
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        )}
      </div>

      {/* Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6 auto-rows-max flex-1 mb-8">
        {visibleCards.map((card, index) => {
          const isOwned = card.quantity > 0;
          const displayName = card.card_name || card.name; 
          const oracleId = card.oracle_id;

          return (
            <button
              key={`${oracleId || displayName}-${index}`}
              onClick={() => onCardClick(card)}
              className={`group relative overflow-hidden rounded-xl border border-border transition-all hover:border-primary hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-primary ${
                !isOwned ? 'opacity-50 grayscale' : ''
              }`}
            >
              <div className="relative w-full aspect-[2.5/3.5] bg-muted rounded-xl overflow-hidden flex items-center justify-center border border-border/50 shadow-xl">
                {card.oracle_id ? (
                  <img
                    src={`${API_BASE_URL}/images/${card.oracle_id}.jpg`}
                    alt={card.card_name}
                    className="w-full h-full object-contain"
                    onError={(e) => {
                      e.currentTarget.style.display = 'none';
                    }}
                  />
                ) : (
                  <span className="text-sm text-zinc-500">Image not found</span>
                )}
              </div>

              {card.quantity >= 2 && (
                <div className="absolute bottom-2 left-2 bg-indigo-600 text-white rounded-full w-8 h-8 flex items-center justify-center text-sm font-bold shadow-md border border-indigo-400 z-30">
                  {card.quantity}
                </div>
              )}

              {/* Hover Overlay */}
              <div className="absolute inset-0 bg-black/80 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-end p-3 z-20 text-left">
                <p className="text-sm font-bold text-white line-clamp-2">{displayName}</p>
                {card.type_line && (
                  <p className="text-xs text-zinc-300 truncate mt-1">{card.type_line}</p>
                )}
                
                {preferences[card.oracle_id] && (
                   <div className="mt-2 pt-2 border-t border-zinc-600 text-xs text-indigo-300">
                     <p>Status: {preferences[card.oracle_id].status}</p>
                     <p>Condition: {preferences[card.oracle_id].condition}</p>
                   </div>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {/* Bottom Main Controls */}
      {totalPages > 1 && (
        <div className="flex justify-center items-center py-6 border-t border-border gap-4 mt-auto">
          <Button 
            variant="outline" 
            onClick={() => handlePageChange(Math.max(currentPage - 1, 1))}
            disabled={currentPage === 1}
          >
            <ChevronLeft className="w-4 h-4 mr-2" />
            Previous
          </Button>
          <span className="text-zinc-400 text-sm font-medium">
            Page {currentPage} of {totalPages}
          </span>
          <Button 
            variant="outline" 
            onClick={() => handlePageChange(Math.min(currentPage + 1, totalPages))}
            disabled={currentPage === totalPages}
          >
            Next
            <ChevronRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
      )}
    </div>
  );
}