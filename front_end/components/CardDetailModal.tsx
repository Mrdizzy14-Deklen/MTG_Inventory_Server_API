'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { X } from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://vm.deklenn.dev';

export interface Card {
  card_name?: string;
  name?: string;
  oracle_id?: string;
  quantity?: number;
  [key: string]: any;
}

interface CardDetailModalProps {
  card: Card;
  isOpen: boolean;
  onClose: () => void;
  onUpdatePreference: (
    oracleId: string,
    preference: string,
    title: string,
    notes: string
  ) => Promise<void>;
  currentPreference?: any;
}

type PreferenceType = 'For Trade' | 'Looking For' | 'Not For Trade' | null;

export function CardDetailModal({
  card,
  isOpen,
  onClose,
  onUpdatePreference,
  currentPreference
}: CardDetailModalProps) {
  const [selectedPreference, setSelectedPreference] = useState<PreferenceType>(null);
  const [title, setTitle] = useState('');
  const [notes, setNotes] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      if (currentPreference) {
        
        const reverseEnumMap: Record<string, string> = {
          'for_trade': 'For Trade',
          'looking_for': 'Looking For',
          'not_for_trade': 'Not For Trade'
        };

        const mappedStatus = reverseEnumMap[currentPreference.status] as PreferenceType;

        setSelectedPreference(mappedStatus || null);
        setTitle(currentPreference.tag || '');
        setNotes(currentPreference.notes || '');
      } else {
        setSelectedPreference(null);
        setTitle('');
        setNotes('');
      }
    }
  }, [isOpen, currentPreference]);

  const handlePreferenceChange = (preference: PreferenceType) => {
    setSelectedPreference(preference);
  };

  const displayName = card.card_name || card.name || 'Unknown Card';

  const handleUpdatePreference = async () => {
    if (!selectedPreference || !card.oracle_id) return;
    setIsLoading(true);
    try {
      await onUpdatePreference(card.oracle_id, selectedPreference, title, notes);
      onClose();
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  const isOwned = (card.quantity || 0) > 0;
  const isPreferenceSelected = selectedPreference !== null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-card rounded-lg border border-border w-full max-w-4xl max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-start p-6 border-b border-border">
          <h2 className="text-2xl font-bold text-foreground">{displayName}</h2>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <X size={24} />
          </button>
        </div>

        <div className="flex gap-8 p-6">
          {/* Card Image */}
          <div className="flex-shrink-0">
            <div className="relative w-64 h-89 rounded-lg bg-muted overflow-hidden border border-border flex items-center justify-center shadow-lg">
              {card.oracle_id ? (
                <img
                  src={`${API_BASE_URL}/images/${card.oracle_id}.jpg`}
                  alt={displayName}
                  className="w-full h-full object-contain"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none';
                  }}
                />
              ) : (
                <span className="text-muted-foreground">No image available</span>
              )}
            </div>
            {isOwned && (
              <div className="mt-3 text-center text-sm font-semibold text-indigo-400">
                Quantity Owned: {card.quantity}
              </div>
            )}
          </div>

          {/* Trade Preference Panel */}
          <div className="flex-1 space-y-6">
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-foreground">Trade Preference</h3>

              <div className="space-y-3">
                {/* For Trade - only if owned */}
                <div className="flex items-center space-x-3">
                  <Checkbox
                    id="for-trade"
                    checked={selectedPreference === 'For Trade'}
                    onCheckedChange={() =>
                      handlePreferenceChange(
                        selectedPreference === 'For Trade' ? null : 'For Trade'
                      )
                    }
                    disabled={!isOwned}
                  />
                  <Label
                    htmlFor="for-trade"
                    className={`cursor-pointer ${!isOwned ? 'opacity-50 cursor-not-allowed text-muted-foreground' : ''}`}
                  >
                    For Trade {(!isOwned) && "(You don't own this)"}
                  </Label>
                </div>

                {/* Looking For */}
                <div className="flex items-center space-x-3">
                  <Checkbox
                    id="looking-for"
                    checked={selectedPreference === 'Looking For'}
                    onCheckedChange={() =>
                      handlePreferenceChange(
                        selectedPreference === 'Looking For' ? null : 'Looking For'
                      )
                    }
                  />
                  <Label htmlFor="looking-for" className="cursor-pointer">
                    Looking For
                  </Label>
                </div>

                {/* Not For Trade - only if owned */}
                <div className="flex items-center space-x-3">
                  <Checkbox
                    id="not-for-trade"
                    checked={selectedPreference === 'Not For Trade'}
                    onCheckedChange={() =>
                      handlePreferenceChange(
                        selectedPreference === 'Not For Trade' ? null : 'Not For Trade'
                      )
                    }
                    disabled={!isOwned}
                  />
                  <Label
                    htmlFor="not-for-trade"
                    className={`cursor-pointer ${!isOwned ? 'opacity-50 cursor-not-allowed text-muted-foreground' : ''}`}
                  >
                    Not For Trade {(!isOwned) && "(You don't own this)"}
                  </Label>
                </div>

              </div>
            </div>

            {/* Title and Notes - grayed out until preference selected */}
            <div
              className={`space-y-4 p-4 rounded-lg bg-muted/20 border border-border transition-opacity ${
                !isPreferenceSelected ? 'opacity-50 pointer-events-none' : ''
              }`}
            >
              <div className="space-y-2">
                <Label htmlFor="trade-title" className="text-sm font-semibold">
                  Trade Title (Optional)
                </Label>
                <Input
                  id="trade-title"
                  placeholder="e.g., 'Trading for value'"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  disabled={!isPreferenceSelected}
                  className="bg-background border-border text-foreground disabled:opacity-50"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="trade-notes" className="text-sm font-semibold">
                  Notes (Optional)
                </Label>
                <Textarea
                  id="trade-notes"
                  placeholder="Add any notes about this trade..."
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  disabled={!isPreferenceSelected}
                  className="bg-background border-border text-foreground min-h-24 resize-none disabled:opacity-50"
                />
              </div>

              <Button
                onClick={handleUpdatePreference}
                disabled={!isPreferenceSelected || isLoading}
                className="w-full bg-primary text-primary-foreground hover:bg-primary/90"
              >
                {isLoading ? 'Updating...' : 'Update Preference'}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}