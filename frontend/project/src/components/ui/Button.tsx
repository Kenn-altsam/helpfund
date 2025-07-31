import React from 'react';
import { cn } from '@/lib/utils';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link';
  size?: 'default' | 'sm' | 'lg' | 'icon';
  children: React.ReactNode;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'default', ...props }, ref) => {
    return (
      <button
        className={cn(
          'inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 touch-manipulation',
          {
            'bg-primary text-primary-foreground hover:bg-primary/90 active:bg-primary/80': variant === 'default',
            'bg-destructive text-destructive-foreground hover:bg-destructive/90 active:bg-destructive/80': variant === 'destructive',
            'border border-input bg-background hover:bg-accent hover:text-accent-foreground active:bg-accent/80': variant === 'outline',
            'bg-secondary text-secondary-foreground hover:bg-secondary/80 active:bg-secondary/60': variant === 'secondary',
            'hover:bg-accent hover:text-accent-foreground active:bg-accent/80': variant === 'ghost',
            'text-primary underline-offset-4 hover:underline': variant === 'link',
          },
          {
            'h-10 px-4 py-2 min-h-[44px]': size === 'default',
            'h-9 rounded-md px-3 min-h-[44px]': size === 'sm',
            'h-11 rounded-md px-8 min-h-[44px]': size === 'lg',
            'h-10 w-10 min-h-[44px] min-w-[44px]': size === 'icon',
          },
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);

Button.displayName = 'Button';

export { Button };