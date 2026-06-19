'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ChevronLeft, Check, X } from 'lucide-react';
import { addBulk, removeBulk } from '@/lib/mtg-client';

export default function BulkManagePage() {
  const [cardNames, setCardNames] = useState('');
  const [feedback, setFeedback] = useState<{
    type: 'success' | 'error' | null;
    errors?: string[];
  }>({
    type: null,
  });
  const [isLoading, setIsLoading] = useState(false);

  const handleAddCards = async () => {
    if (!cardNames.trim()) return;

    setIsLoading(true);
    setFeedback({ type: null });

    try {
      const cards = cardNames.split('\n').filter(line => line.trim() !== '').map(line => {
        const trimmedLine = line.trim();
        const firstSpaceIndex = trimmedLine.indexOf(' ');
        
        const firstPart = trimmedLine.substring(0, firstSpaceIndex);
        const isQuantity = firstPart.length > 0 && /^\d+$/.test(firstPart);

        if (isQuantity && firstSpaceIndex !== -1) {
          return {
            name: trimmedLine.substring(firstSpaceIndex + 1).trim(),
            quantity: parseInt(firstPart, 10)
          };
        }
        
        return {
          name: trimmedLine,
          quantity: 1
        };
      });

      const result = await addBulk(cards);

      if (result.status === 'success') {
        setFeedback({ type: 'success' });
        setCardNames('');
      } else {
        setFeedback({
          type: 'error',
          errors: result.errors || [result.message || 'An error occurred'],
        });
      }
    } catch (error: any) {
      console.error('Add bulk failed:', error);
      setFeedback({
        type: 'error',
        errors: [error.message || 'Failed to connect to server'],
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleRemoveCards = async () => {
    if (!cardNames.trim()) return;

    setIsLoading(true);
    setFeedback({ type: null });

    try {
      const cards = cardNames.split('\n').filter(line => line.trim() !== '').map(line => {
        const trimmedLine = line.trim();
        const firstSpaceIndex = trimmedLine.indexOf(' ');
        
        const firstPart = trimmedLine.substring(0, firstSpaceIndex);
        const isQuantity = firstPart.length > 0 && /^\d+$/.test(firstPart);

        if (isQuantity && firstSpaceIndex !== -1) {
          return {
            name: trimmedLine.substring(firstSpaceIndex + 1).trim(),
            quantity: parseInt(firstPart, 10)
          };
        }
        
        return {
          name: trimmedLine,
          quantity: 1
        };
      });

      const result = await removeBulk(cards);

      if (result.status === 'success') {
        setFeedback({ type: 'success' });
        setCardNames('');
      } else {
        setFeedback({
          type: 'error',
          errors: result.errors || [result.message || 'An error occurred during removal'],
        });
      }
    } catch (error: any) {
      console.error('Remove bulk failed:', error);
      setFeedback({
        type: 'error',
        errors: [error.message || 'Failed to connect to server'],
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-4 mb-8">
          <Link href="/">
            <Button
              variant="ghost"
              size="icon"
              className="text-muted-foreground hover:text-foreground"
            >
              <ChevronLeft size={24} />
            </Button>
          </Link>
          <h1 className="text-3xl font-bold text-foreground">Add/Remove Cards</h1>
        </div>

        {/* Main Card */}
        <div className="bg-card border border-border rounded-lg p-8 space-y-6">
          <p className="text-muted-foreground">
            Enter card names (one per line) to add or remove from your collection.
          </p>

          {/* Textarea */}
          <Textarea
            placeholder="Enter card names here (one per line)&#10;Example:&#10;Black Lotus&#10;Lightning Bolt&#10;Counterspell"
            value={cardNames}
            onChange={(e) => setCardNames(e.target.value)}
            disabled={isLoading}
            className="bg-background border-border text-foreground min-h-64 resize-none disabled:opacity-50"
          />

          {/* Feedback */}
          {feedback.type === 'success' && (
            <div className="flex items-center gap-2 p-4 bg-green-500/10 border border-green-500/20 rounded-lg">
              <Check className="text-green-500" size={20} />
              <span className="text-green-500 font-medium">Cards updated successfully!</span>
            </div>
          )}

          {feedback.type === 'error' && (
            <div className="space-y-2">
              <div className="flex items-center gap-2 p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
                <X className="text-red-500" size={20} />
                <span className="text-red-500 font-medium">
                  {feedback.errors && feedback.errors.length > 0
                    ? 'Some cards could not be processed:'
                    : 'Operation failed'}
                </span>
              </div>
              {feedback.errors && feedback.errors.length > 0 && (
                <div className="p-4 bg-muted/30 border border-border rounded-lg">
                  <ul className="space-y-1">
                    {feedback.errors.map((error, idx) => (
                      <li key={idx} className="text-sm text-muted-foreground">
                        • {error}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Buttons */}
          <div className="flex gap-4">
            <Button
              onClick={handleAddCards}
              disabled={isLoading || !cardNames.trim()}
              className="flex-1 bg-primary text-primary-foreground hover:bg-primary/90"
            >
              {isLoading ? 'Processing...' : 'Add Cards'}
            </Button>
            <Button
              onClick={handleRemoveCards}
              disabled={isLoading || !cardNames.trim()}
              variant="outline"
              className="flex-1 border-border hover:bg-muted text-foreground"
            >
              {isLoading ? 'Processing...' : 'Remove Cards'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
