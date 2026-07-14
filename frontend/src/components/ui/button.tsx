import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "rounded-full bg-primary text-primary-foreground hover:bg-primary/90",
        auth: "rounded-[10px] bg-[var(--auth-action)] text-white hover:bg-[var(--auth-action-hover)] focus-visible:ring-[var(--auth-action)]/30",
        brand: "rounded-[10px] bg-[var(--action)] text-white hover:bg-[var(--action-hover)] focus-visible:ring-[var(--action)]/30",
        brandGrad:
          "rounded-[10px] bg-[image:var(--brand-grad)] text-white shadow-[0_6px_18px_rgba(203,107,61,0.35)] transition-[box-shadow,transform] hover:shadow-[0_10px_26px_rgba(203,107,61,0.45)] hover:-translate-y-px focus-visible:ring-[var(--action)]/40",
        authOutline:
          "rounded-[10px] border border-[var(--auth-line)] bg-transparent text-[var(--auth-muted)] hover:border-[color:rgb(203_107_61/0.4)] hover:text-[var(--auth-text)]",
        outline:
          "rounded-full border border-border bg-transparent text-foreground hover:bg-nav-on",
        ghost: "rounded-lg hover:bg-nav-on hover:text-foreground",
      },
      size: {
        default: "h-10 px-5",
        sm: "h-8 px-4 text-xs",
        lg: "h-11 px-8",
        icon: "h-9 w-9 rounded-full",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
