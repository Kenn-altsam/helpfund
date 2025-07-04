import { Heart } from 'lucide-react';
import { Skeleton } from '@/components/ui/Skeleton';

export function LoadingScreen() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-primary/5 via-background to-secondary/5">
      <div className="text-center">
        <Heart className="h-12 w-12 text-primary mx-auto mb-6 animate-pulse" />
        <div className="space-y-4">
          <Skeleton className="h-8 w-64 mx-auto" />
          <Skeleton className="h-4 w-48 mx-auto" />
        </div>
      </div>
    </div>
  );
} 