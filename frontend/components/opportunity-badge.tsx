// frontend/components/opportunity-badge.tsx
import { Circle } from 'lucide-react';
import type { ReferenceOpportunity } from '@/lib/types';

interface OpportunityBadgeProps {
    opportunity: ReferenceOpportunity;
    compact?: boolean;
}

// Translate backend opportunity values into concise, consistent visual labels.
export function OpportunityBadge({ opportunity, compact = false }: OpportunityBadgeProps) {
    const styles = {
        'strong reference opportunity': 'bg-violet-100 text-violet-700 ring-violet-200',
        'possible reference opportunity': 'bg-amber-50 text-amber-700 ring-amber-200',
        'no reference needed': 'bg-slate-100 text-slate-600 ring-slate-200',
    }[opportunity];
    const label = {
        'strong reference opportunity': compact ? 'Strong' : 'Strong Opportunity',
        'possible reference opportunity': compact ? 'Possible' : 'Possible Opportunity',
        'no reference needed': compact ? 'No Match' : 'No Reference Needed',
    }[opportunity];

    return (
        <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 ring-inset ${styles}`}>
            <Circle size={7} fill="currentColor" strokeWidth={0} aria-hidden="true" />
            {label}
        </span>
    );
}

