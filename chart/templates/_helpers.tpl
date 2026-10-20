{{- define "lcl.gatewayRef" -}}
aiGatewayRef: { group: aigateway.konghq.com, kind: OnPremAIGateway, namespacedRef: { name: {{ .Values.gateway }} } }
{{- end }}

{{- define "lcl.labels" -}}
{ app.kubernetes.io/part-of: lcl-aigw }
{{- end }}
