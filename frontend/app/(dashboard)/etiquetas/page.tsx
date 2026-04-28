'use client'
import { useState, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Header } from '@/components/layout/Header'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { etiquetas as etiquetasApi, config as configApi } from '@/lib/api'
import { Tag, Printer, QrCode } from 'lucide-react'

type Item = { id: number; num_tag: string; localizacao: string; quantidade: number; descricao: string }

export default function EtiquetasPage() {
  const [tipoMaterial, setTipoMaterial] = useState('')
  const [codigoSel, setCodigoSel] = useState('')
  const [qtdCopias, setQtdCopias] = useState('1')
  const printRef = useRef<HTMLDivElement>(null)

  const { data: cfg } = useQuery({
    queryKey: ['configuracoes'],
    queryFn: () => configApi.get() as Promise<{ tipos_material: string[] }>,
  })

  const { data: produtosFiltrados = [] } = useQuery({
    queryKey: ['etiquetas-produtos', tipoMaterial],
    queryFn: () => etiquetasApi.produtos(tipoMaterial),
    enabled: !!tipoMaterial,
  })

  const { data: inventario = [] } = useQuery({
    queryKey: ['etiquetas-inventario', codigoSel],
    queryFn: () => etiquetasApi.inventario(codigoSel) as Promise<Item[]>,
    enabled: !!codigoSel,
  })

  const tiposMaterial = cfg?.tipos_material ?? []

  function handlePrint() {
    const win = window.open('', '', 'width=800,height=600')
    if (!win || !printRef.current) return
    win.document.write(`
      <html><head><title>Etiquetas TraceBox</title>
      <style>
        body { margin: 0; font-family: Arial, sans-serif; }
        .etiqueta { border: 2px solid #000; padding: 8px; margin: 4px; display: inline-block; width: 160px; text-align: center; page-break-inside: avoid; }
        .tag { font-size: 18px; font-weight: bold; }
        .info { font-size: 10px; color: #333; }
        @media print { .etiqueta { page-break-inside: avoid; } }
      </style></head><body>
      ${printRef.current.innerHTML}
      </body></html>
    `)
    win.document.close()
    win.print()
  }

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <Header title="Etiquetas" subtitle="Geração e impressão de etiquetas / QR Codes" />
      <main className="flex-1 overflow-y-auto p-4 space-y-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Tag className="h-4 w-4 text-primary" /> Configurar Impressão
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="space-y-1.5">
                <Label>Tipo de Material</Label>
                <Select value={tipoMaterial} onValueChange={v => { setTipoMaterial(v); setCodigoSel('') }}>
                  <SelectTrigger><SelectValue placeholder="Selecione…" /></SelectTrigger>
                  <SelectContent>{tiposMaterial.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Produto</Label>
                <Select value={codigoSel} onValueChange={setCodigoSel} disabled={!tipoMaterial}>
                  <SelectTrigger><SelectValue placeholder="Selecione o produto…" /></SelectTrigger>
                  <SelectContent>
                    {(produtosFiltrados as { codigo: string; descricao: string }[]).map(p => (
                      <SelectItem key={p.codigo} value={p.codigo}>{p.codigo} — {p.descricao}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Cópias por Etiqueta</Label>
                <Input type="number" min="1" max="10" value={qtdCopias} onChange={e => setQtdCopias(e.target.value)} />
              </div>
            </div>

            {inventario.length > 0 && (
              <div className="flex gap-2">
                <Button onClick={handlePrint} size="sm">
                  <Printer className="h-4 w-4 mr-1" /> Imprimir Etiquetas
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {codigoSel && inventario.length === 0 && (
          <Alert><AlertDescription>Nenhum item em estoque para o produto selecionado.</AlertDescription></Alert>
        )}

        {inventario.length > 0 && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <QrCode className="h-4 w-4 text-primary" /> Pré-visualização — {inventario.length} etiqueta(s)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div ref={printRef} className="flex flex-wrap gap-3">
                {inventario.flatMap((item, idx) =>
                  Array.from({ length: parseInt(qtdCopias) || 1 }, (_, ci) => (
                    <div key={`${idx}-${ci}`} className="border border-border rounded-lg p-3 w-40 text-center space-y-1">
                      <div className="flex justify-center">
                        <QrCode className="h-12 w-12 text-foreground opacity-80" />
                      </div>
                      <p className="text-sm font-bold text-foreground">{item.num_tag || codigoSel}</p>
                      <p className="text-[10px] text-muted-foreground leading-tight">{item.descricao}</p>
                      <p className="text-[10px] text-muted-foreground">{item.localizacao}</p>
                      {item.quantidade > 1 && <p className="text-[10px] font-medium text-primary">Qtd: {item.quantidade}</p>}
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  )
}
