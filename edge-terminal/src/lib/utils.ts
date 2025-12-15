import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}

export function formatNumber(num: number | null | undefined, decimals = 2): string {
    if (num === null || num === undefined) return '-';
    return num.toFixed(decimals);
}

export function formatDate(timestamp: number | null | undefined): string {
    if (!timestamp) return '-';
    return new Date(timestamp * 1000).toLocaleString();
}
