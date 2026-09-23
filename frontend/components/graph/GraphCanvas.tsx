'use client';

import { useMemo } from 'react';
import { Background, Controls, Handle, MiniMap, Position, ReactFlow, type Edge, type NodeProps, type Node } from '@xyflow/react';
import type { GraphEntity, GraphRelationship } from '@/types';

type EntityNodeData = { entity: GraphEntity };

function EntityNode({ data, selected }: NodeProps<Node<EntityNodeData>>) {
  const { entity } = data;
  const palette: Record<GraphEntity['type'], string> = { Customer: 'border-blue-200 bg-blue-50 text-blue-700', Account: 'border-slate-200 bg-slate-50 text-slate-700', Transaction: 'border-red-200 bg-red-50 text-red-700', Device: 'border-orange-200 bg-orange-50 text-orange-700', Merchant: 'border-amber-200 bg-amber-50 text-amber-700', IP: 'border-violet-200 bg-violet-50 text-violet-700', Case: 'border-cyan-200 bg-cyan-50 text-cyan-700' };
  return <div className={`min-w-[148px] rounded-xl border bg-white px-3 py-2.5 shadow-sm transition ${palette[entity.type]} ${selected ? 'ring-2 ring-blue-500 ring-offset-2' : ''} ${entity.flagged ? 'shadow-[0_0_0_3px_rgba(248,113,113,.10)]' : ''}`}><Handle type="target" position={Position.Left} className="!h-2 !w-2 !border-2 !border-white !bg-slate-400" /><div className="flex items-start gap-2"><div className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-[9px] font-black ${palette[entity.type]}`}>{entity.type.slice(0, 2).toUpperCase()}</div><div className="min-w-0"><div className="truncate font-mono text-[11px] font-bold">{entity.label}</div><div className="mt-0.5 max-w-[110px] truncate text-[9px] text-slate-500">{entity.subtitle}</div></div></div>{entity.risk_score !== undefined && <div className="mt-2 flex items-center gap-2"><div className="h-1 flex-1 overflow-hidden rounded-full bg-slate-200"><div className={`h-full rounded-full ${entity.risk_score > .8 ? 'bg-red-500' : 'bg-amber-400'}`} style={{ width: `${entity.risk_score * 100}%` }} /></div><span className="text-[9px] font-bold text-slate-500">{Math.round(entity.risk_score * 100)}%</span></div>}<Handle type="source" position={Position.Right} className="!h-2 !w-2 !border-2 !border-white !bg-slate-400" /></div>;
}

const nodeTypes = { entity: EntityNode };

export function GraphCanvas({ entities, relationships, selectedEntity, onSelect }: { entities: GraphEntity[]; relationships: GraphRelationship[]; selectedEntity?: string; onSelect: (entityId: string) => void }) {
  const nodes = useMemo<Node<EntityNodeData>[]>(() => {
    const positions: Record<string, { x: number; y: number }> = { 'C-45821': { x: 40, y: 160 }, 'A-7712': { x: 270, y: 160 }, 'TXN-104829': { x: 510, y: 160 }, 'D-421': { x: 510, y: 10 }, 'M-908': { x: 750, y: 230 }, 'IP-771': { x: 750, y: 20 }, 'CASE-1024': { x: 750, y: 90 } };
    return entities.map((entity) => ({ id: entity.id, type: 'entity', position: positions[entity.id] ?? { x: 200, y: 200 }, data: { entity }, selected: entity.id === selectedEntity }));
  }, [entities, selectedEntity]);
  const edges = useMemo<Edge[]>(() => relationships.map((relationship) => ({ id: relationship.id, source: relationship.source, target: relationship.target, label: relationship.label, type: 'smoothstep', animated: Boolean(relationship.suspicious), style: { stroke: relationship.suspicious ? '#ef6a64' : '#a9b7c7', strokeWidth: relationship.suspicious ? 2.2 : 1.4 }, labelStyle: { fill: relationship.suspicious ? '#c44943' : '#8492a5', fontSize: 9, fontWeight: 600 }, labelBgStyle: { fill: '#fff', fillOpacity: 0.92 }, labelBgPadding: [4, 2] as [number, number] })), [relationships]);
  return <div className="h-[398px] w-full"><ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView fitViewOptions={{ padding: 0.18 }} onNodeClick={(_, node) => onSelect(node.id)} proOptions={{ hideAttribution: true }}><Background color="#dbe3ed" gap={22} size={1} /><Controls showInteractive={false} /><MiniMap nodeColor={(node) => node.id === selectedEntity ? '#2563eb' : '#cbd5e1'} maskColor="rgba(244,247,251,.7)" /></ReactFlow></div>;
}
