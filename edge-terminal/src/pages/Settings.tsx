import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { healthApi, manualLogApi } from '../services/api';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Activity, Database, Server, Save, CheckCircle2, AlertCircle } from 'lucide-react';
import { cn } from '../lib/utils';

const Settings: React.FC = () => {
    const [formData, setFormData] = useState({
        ring_number: '',
        pitch: '',
        roll: '',
        remarks: ''
    });
    const [submitStatus, setSubmitStatus] = useState<'idle' | 'success' | 'error'>('idle');

    // 健康检查查询
    const { data: health, refetch: refetchHealth } = useQuery({
        queryKey: ['health'],
        queryFn: healthApi.checkEdgeHealth,
        refetchInterval: 30000,
    });

    // 手动日志提交
    const logMutation = useMutation({
        mutationFn: (data: any) => manualLogApi.submitManualLogs(data),
        onSuccess: () => {
            setSubmitStatus('success');
            setTimeout(() => setSubmitStatus('idle'), 3000);
            setFormData({ ring_number: '', pitch: '', roll: '', remarks: '' });
        },
        onError: () => {
            setSubmitStatus('error');
            setTimeout(() => setSubmitStatus('idle'), 3000);
        }
    });

    const handleManualSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!formData.ring_number) return;

        const payload = {
            operator_id: "OP-001",
            remarks: formData.remarks,
            attitude_logs: [
                {
                    pitch: parseFloat(formData.pitch || '0'),
                    roll: parseFloat(formData.roll || '0'),
                    ring_number: parseInt(formData.ring_number),
                    timestamp: Date.now() / 1000
                }
            ]
        };

        logMutation.mutate(payload);
    };

    return (
        <div className="space-y-6">
            <div className="flex flex-col gap-2">
                <h1 className="text-2xl font-bold tracking-tight text-white">系统设置</h1>
                <p className="text-text-secondary">系统状态监控与手动数据录入</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* 系统健康面板 */}
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Activity className="w-5 h-5 text-primary" />
                            系统健康状态
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="flex items-center justify-between p-3 rounded-lg bg-background border border-border">
                            <div className="flex items-center gap-3">
                                <div className="p-2 rounded-full bg-success/10 text-success">
                                    <Server className="w-4 h-4" />
                                </div>
                                <div>
                                    <p className="font-medium text-sm">边缘API服务</p>
                                    <p className="text-xs text-text-secondary">端口: 8000</p>
                                </div>
                            </div>
                            <Badge variant={health?.status === 'healthy' ? 'success' : 'destructive'}>
                                {health?.status === 'healthy' ? '正常' : '异常'}
                            </Badge>
                        </div>

                        <div className="flex items-center justify-between p-3 rounded-lg bg-background border border-border">
                            <div className="flex items-center gap-3">
                                <div className="p-2 rounded-full bg-primary/10 text-primary">
                                    <Database className="w-4 h-4" />
                                </div>
                                <div>
                                    <p className="font-medium text-sm">本地数据库</p>
                                    <p className="text-xs text-text-secondary">SQLite</p>
                                </div>
                            </div>
                            <Badge variant="success">已连接</Badge>
                        </div>

                        <Button
                            variant="outline"
                            className="w-full mt-2"
                            onClick={() => refetchHealth()}
                        >
                            运行诊断
                        </Button>
                    </CardContent>
                </Card>

                {/* 手动数据录入 */}
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Save className="w-5 h-5 text-warning" />
                            手动数据录入
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <form onSubmit={handleManualSubmit} className="space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-1">
                                    <label className="text-xs font-medium text-text-secondary">环号</label>
                                    <input
                                        type="number"
                                        className="w-full h-9 rounded-md border border-border bg-background px-3 text-sm focus:ring-1 focus:ring-primary outline-none text-text-primary"
                                        value={formData.ring_number}
                                        onChange={e => setFormData({ ...formData, ring_number: e.target.value })}
                                        required
                                    />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs font-medium text-text-secondary">备注</label>
                                    <input
                                        type="text"
                                        className="w-full h-9 rounded-md border border-border bg-background px-3 text-sm focus:ring-1 focus:ring-primary outline-none text-text-primary"
                                        value={formData.remarks}
                                        onChange={e => setFormData({ ...formData, remarks: e.target.value })}
                                    />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs font-medium text-text-secondary">俯仰角 (°)</label>
                                    <input
                                        type="number" step="0.01"
                                        className="w-full h-9 rounded-md border border-border bg-background px-3 text-sm focus:ring-1 focus:ring-primary outline-none text-text-primary"
                                        value={formData.pitch}
                                        onChange={e => setFormData({ ...formData, pitch: e.target.value })}
                                    />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs font-medium text-text-secondary">横滚角 (°)</label>
                                    <input
                                        type="number" step="0.01"
                                        className="w-full h-9 rounded-md border border-border bg-background px-3 text-sm focus:ring-1 focus:ring-primary outline-none text-text-primary"
                                        value={formData.roll}
                                        onChange={e => setFormData({ ...formData, roll: e.target.value })}
                                    />
                                </div>
                            </div>

                            <Button
                                type="submit"
                                className={cn("w-full transition-all", submitStatus === 'error' ? "bg-error hover:bg-error/90" : "")}
                                disabled={submitStatus === 'success' || logMutation.isPending}
                            >
                                {logMutation.isPending ? (
                                    <span className="flex items-center gap-2">保存中...</span>
                                ) : submitStatus === 'success' ? (
                                    <span className="flex items-center gap-2">
                                        <CheckCircle2 className="w-4 h-4" /> 保存成功
                                    </span>
                                ) : submitStatus === 'error' ? (
                                    <span className="flex items-center gap-2">
                                        <AlertCircle className="w-4 h-4" /> 保存失败
                                    </span>
                                ) : '提交数据'}
                            </Button>
                        </form>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
};

export default Settings;
