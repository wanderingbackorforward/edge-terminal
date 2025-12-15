import React from 'react';
import { Outlet } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';

export const Layout: React.FC = () => {
    return (
        <div className="min-h-screen bg-background text-text-primary font-sans selection:bg-primary/30">
            <Header />
            <div className="flex">
                <Sidebar />
                <main className="flex-1 p-6 overflow-y-auto h-[calc(100vh-4rem)]">
                    <div className="max-w-7xl mx-auto">
                        <Outlet />
                    </div>
                </main>
            </div>
        </div>
    );
};
