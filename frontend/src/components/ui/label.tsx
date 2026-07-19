import * as React from "react";

import { cn } from "@/lib/utils";

const Label = React.forwardRef<
  HTMLLabelElement,
  React.ComponentProps<"label">
>(({ className, ...props }, ref) => (
  <label
    ref={ref}
    className={cn(
      "mb-1.5 block text-xs font-medium text-muted-foreground",
      className,
    )}
    {...props}
  />
));
Label.displayName = "Label";

export { Label };
