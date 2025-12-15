import React, { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { cn } from '../../lib/utils';
import { Button } from './Button';
import { Card, CardTitle } from './Card';

interface DialogProps {
    isOpen: boolean;
    onClose: () => void;
    title?: string;
    description?: string;
    children: React.ReactNode;
}

export const Dialog: React.FC<DialogProps> = ({
    isOpen,
    onClose,
    title,
    description,
    children,
}) => {
    const overlayRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const handleEscape = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };

        if (isOpen) {
            document.addEventListener('keydown', handleEscape);
            document.body.style.overflow = 'hidden';
        }

        return () => {
            document.removeEventListener('keydown', handleEscape);
            document.body.style.overflow = 'unset';
        };
    }, [isOpen, onClose]);

    if (!isOpen) return null;

    return createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm animate-in fade-in-0">
            <div
                ref={overlayRef}
                className="fixed inset-0"
                onClick={onClose}
            />
            <Card className="relative z-50 w-full max-w-lg shadow-lg animate-in fade-in-0 zoom-in-95 bg-surface border-border">
                <div className="flex flex-col space-y-1.5 p-6 pb-4">
                    <div className="flex items-center justify-between">
                        {title && <CardTitle>{title}</CardTitle>}
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6 rounded-full -mr-2"
                            onClick={onClose}
                        >
                            <X className="w-4 h-4" />
                        </Button>
                    </div>
                    {description && (
                        <p className="text-sm text-text-secondary">
                            {description}
                        </p>
                    )}
                </div>
                <div className="p-6 pt-0">
                    {children}
                </div>
            </Card>
        </div>,
        document.body
    );
};
