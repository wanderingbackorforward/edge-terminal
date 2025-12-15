import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
    Table,
    TableHeader,
    TableBody,
    TableHead,
    TableRow,
    TableCell,
    Pagination
} from '../components/ui/Table';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { ringApi } from '../services/api';
import { formatDate, formatNumber, cn } from '../lib/utils';
import { RefreshCw, Download, Database } from 'lucide-react';

const PAGE_SIZE = 15;

const Rings: React.FC = () => {
    const [currentPage, setCurrentPage] = useState(1);

    const { data, isLoading, isError, refetch, isRefetching } = useQuery({
        queryKey: ['rings', 'list', currentPage],
        queryFn: () => ringApi.getRings({ page: currentPage, page_size: PAGE_SIZE }),
        refetchInterval: 30000,
        keepPreviousData: true,
    });

    const totalPages = data ? Math.ceil(data.total / data.page_size) : 0;

    const getSettlementStatus = (val: number | null) => {
        if (val === null) return 'secondary';
        return Math.abs(val) > 5 ? 'destructive' : 'success';
    };

    return (
        <div className="space-y-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
                        环数据查询
                    </h1>
                    <p className="text-text-secondary">
                        T193标段完整施工记录
                    </p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isRefetching}>
                        <RefreshCw className={cn("w-4 h-4 mr-2", isRefetching && "animate-spin")} />
                        刷新
                    </Button>
                    <Button variant="outline" size="sm">
                        <Download className="w-4 h-4 mr-2" />
                        导出CSV
                    </Button>
                </div>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle className="text-base font-medium flex items-center gap-2">
                        <Database className="w-4 h-4 text-primary" />
                        施工日志
                        <Badge variant="secondary" className="ml-2 font-mono">
                            共 {data?.total ?? 0} 条记录
                        </Badge>
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {isError ? (
                        <div className="p-8 text-center text-error border border-error/20 rounded-lg bg-error/5">
                            加载环数据失败，请检查网络连接
                        </div>
                    ) : (
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead className="w-[100px]">环号</TableHead>
                                    <TableHead>完成时间</TableHead>
                                    <TableHead>推进速度</TableHead>
                                    <TableHead>推力</TableHead>
                                    <TableHead>扭矩</TableHead>
                                    <TableHead>沉降</TableHead>
                                    <TableHead className="text-right">操作</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {isLoading ? (
                                    Array(5).fill(0).map((_, i) => (
                                        <TableRow key={i}>
                                            <TableCell><div className="h-4 w-8 bg-surface animate-pulse rounded" /></TableCell>
                                            <TableCell><div className="h-4 w-24 bg-surface animate-pulse rounded" /></TableCell>
                                            <TableCell><div className="h-4 w-16 bg-surface animate-pulse rounded" /></TableCell>
                                            <TableCell><div className="h-4 w-16 bg-surface animate-pulse rounded" /></TableCell>
                                            <TableCell><div className="h-4 w-16 bg-surface animate-pulse rounded" /></TableCell>
                                            <TableCell><div className="h-4 w-8 bg-surface animate-pulse rounded" /></TableCell>
                                            <TableCell><div className="h-8 w-16 bg-surface animate-pulse rounded ml-auto" /></TableCell>
                                        </TableRow>
                                    ))
                                ) : (
                                    data?.rings.map((ring) => (
                                        <TableRow key={ring.ring_number} className="group">
                                            <TableCell className="font-mono font-medium text-primary">
                                                第{ring.ring_number}环
                                            </TableCell>
                                            <TableCell className="text-text-secondary text-xs">
                                                {formatDate(ring.end_time)}
                                            </TableCell>
                                            <TableCell>
                                                {formatNumber(ring.mean_advance_rate, 1)} mm/min
                                            </TableCell>
                                            <TableCell>
                                                {(ring.mean_thrust ?? 0).toLocaleString()} kN
                                            </TableCell>
                                            <TableCell>
                                                {(ring.mean_torque ?? 0).toLocaleString()} kNm
                                            </TableCell>
                                            <TableCell>
                                                <Badge variant={getSettlementStatus(ring.settlement_value)}>
                                                    {ring.settlement_value
                                                        ? `${formatNumber(ring.settlement_value, 1)} mm`
                                                        : '-'}
                                                </Badge>
                                            </TableCell>
                                            <TableCell className="text-right">
                                                <Button variant="ghost" size="sm">详情</Button>
                                            </TableCell>
                                        </TableRow>
                                    ))
                                )}
                            </TableBody>
                        </Table>
                    )}

                    {data && (
                        <Pagination
                            currentPage={currentPage}
                            totalPages={totalPages}
                            onPageChange={setCurrentPage}
                        />
                    )}
                </CardContent>
            </Card>
        </div>
    );
};

export default Rings;
