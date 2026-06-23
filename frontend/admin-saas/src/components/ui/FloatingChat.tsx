import { MessageCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

type FloatingChatProps = {
  onClick?: () => void;
  className?: string;
  label?: string;
};

/** Floating chat launcher — mirrors Django #tf-chat-toggle (Lovable spec). */
export function FloatingChat({ onClick, className, label = 'Open assistant' }: FloatingChatProps) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      className={cn(
        'fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-orange text-white shadow-lg transition hover:scale-105 hover:shadow-xl',
        className,
      )}
    >
      <MessageCircle className="h-6 w-6" aria-hidden />
    </button>
  );
}
