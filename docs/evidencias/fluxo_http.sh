#!/usr/bin/env bash
# Fluxo completo da API via HTTP (requer a API em http://localhost:8000 e o seed aplicado).
B=${BASE_URL:-http://localhost:8000}
j(){ python3 -m json.tool --no-ensure-ascii; }
short(){ python3 -c "
import sys,json; d=json.load(sys.stdin)
def cut(o):
    if isinstance(o,dict): return {k:(f'[{len(v)} pontos]' if k=='polyline' else cut(v)) for k,v in o.items()}
    if isinstance(o,list): return [cut(x) for x in o]
    return o
print(json.dumps(cut(d),indent=2,ensure_ascii=False))"; }
get(){ python3 -c "import sys,json;print(json.load(sys.stdin)$1)"; }
SUF=$RANDOM
HOUR=$(date -u -d '-3 hours' +%Y-%m-%dT%H:%M:%S)   # horário local de São Paulo
FIAP='{"lat":-23.5646,"lng":-46.6528}'; CASA='{"lat":-23.5530,"lng":-46.6525}'
J='Content-Type: application/json'

echo "### 0. Healthcheck"; curl -s $B/health | j
echo "### 1. Cadastro e login (cidadã Leo e vizinha Bia)"
curl -s -X POST $B/auth/register -H "$J" -d "{\"name\":\"Leo Demo\",\"email\":\"leo$SUF@safewalk.dev\",\"password\":\"Cidadao@123\"}" | j
curl -s -X POST $B/auth/register -H "$J" -d "{\"name\":\"Bia Lima\",\"email\":\"bia$SUF@safewalk.dev\",\"password\":\"Cidadao@123\"}" >/dev/null
T=$(curl -s -X POST $B/auth/login -d "username=leo$SUF@safewalk.dev&password=Cidadao@123" | get "['access_token']"); H="Authorization: Bearer $T"
T2=$(curl -s -X POST $B/auth/login -d "username=bia$SUF@safewalk.dev&password=Cidadao@123" | get "['access_token']"); H2="Authorization: Bearer $T2"
echo "-- login com senha errada:"; curl -s -w " (HTTP %{http_code})\n" -X POST $B/auth/login -d "username=leo$SUF@safewalk.dev&password=errada123"
echo "### 2. Define PIN do SOS"; curl -s -o /dev/null -w "HTTP %{http_code}\n" -X PUT $B/users/me/pin -H "$H" -H "$J" -d '{"pin":"4821"}'
echo "### 3. Convida contato; só depois de aceitar ele pode acompanhar"
C=$(curl -s -X POST $B/contacts -H "$H" -H "$J" -d '{"name":"Mãe","phone":"+5511999990000"}'); echo "$C" | j
CID=$(echo "$C" | get "['id']"); TOK=$(echo "$C" | get "['invite_token']")
echo "-- trajeto com contato ainda pendente:"
curl -s -w " (HTTP %{http_code})\n" -X POST $B/trips -H "$H" -H "$J" -d "{\"origin\":$FIAP,\"destination\":$CASA,\"contact_ids\":[$CID]}"
curl -s -X POST $B/contacts/accept/$TOK | j
echo "### 4. Relato colaborativo na R. Augusta: criado por Leo, confirmado por Bia"
R=$(curl -s -X POST $B/reports -H "$H" -H "$J" -d '{"lat":-23.5560,"lng":-46.6600,"type":"roubo_celular","details":"dois homens de moto"}'); echo "$R" | j
RID=$(echo "$R" | get "['id']")
echo "-- Bia confirma (peso sobe):"; curl -s -X POST $B/reports/$RID/confirm -H "$H2" | j
echo "-- Leo tenta confirmar o próprio relato:"; curl -s -w " (HTTP %{http_code})\n" -X POST $B/reports/$RID/confirm -H "$H"
echo "### 5. Score de risco na R. Augusta (23h) com o relato ativo"
curl -s "$B/risk/score?lat=-23.5560&lng=-46.6600&hour=23" -H "$H" | j
echo "### 5b. Compara rota rápida x segura (FIAP -> Frei Caneca), horário local $HOUR"
curl -s -X POST $B/routes/compare -H "$H" -H "$J" -d "{\"origin\":$FIAP,\"destination\":$CASA,\"depart_at\":\"$HOUR\"}" | short
echo "### 6. Inicia trajeto acompanhado pela rota segura"
TR=$(curl -s -X POST $B/trips -H "$H" -H "$J" -d "{\"origin\":$FIAP,\"destination\":$CASA,\"route_type\":\"safe\",\"contact_ids\":[$CID]}"); echo "$TR" | short
TID=$(echo "$TR" | get "['id']"); STOK=$(echo "$TR" | get "['shares'][0]['token']")
echo "### 7. Envia localização e o contato abre o link público (sem login)"
curl -s -X POST $B/trips/$TID/locations -H "$H" -H "$J" -d '{"lat":-23.5640,"lng":-46.6527}' | j
curl -s $B/public/track/$STOK | short
echo "-- posição longe da rota (desvio):"; curl -s -X POST $B/trips/$TID/locations -H "$H" -H "$J" -d '{"lat":-23.5900,"lng":-46.6100}' | j
echo "### 8. SOS automático por desvio: pergunta -> escalada -> cancelamento com PIN"
S=$(curl -s -X POST $B/sos -H "$H" -H "$J" -d "{\"lat\":-23.5640,\"lng\":-46.6527,\"trigger\":\"auto_deviation\",\"trip_id\":$TID}"); echo "$S" | j
SID=$(echo "$S" | get "['id']")
echo "-- escala para contatos:"; curl -s -X POST $B/sos/$SID/escalate -H "$H" | j
echo "-- cancelar com PIN errado:"; curl -s -w " (HTTP %{http_code})\n" -X POST $B/sos/$SID/cancel -H "$H" -H "$J" -d '{"pin":"0000"}'
echo "-- cancelar com PIN correto:"; curl -s -X POST $B/sos/$SID/cancel -H "$H" -H "$J" -d '{"pin":"4821"}' | j
echo "### 9. Finaliza trajeto; link do contato mostra chegada"
curl -s -X POST $B/trips/$TID/complete -H "$H" | short
curl -s $B/public/track/$STOK | short
echo "### 10. Painel da Prefeitura (operador) e bloqueio para cidadão"
OT=$(curl -s -X POST $B/auth/login -d 'username=operador@safewalk.dev&password=Operador@123' | get "['access_token']")
curl -s $B/dashboard/overview -H "Authorization: Bearer $OT" | j
echo "-- cidadão no painel:"; curl -s -w " (HTTP %{http_code})\n" $B/dashboard/overview -H "$H"
echo "-- operador marca o relato como falso (reputação do autor cai):"
curl -s -X PATCH $B/reports/$RID/resolve -H "Authorization: Bearer $OT" -H "$J" -d '{"status":"false_report"}' | j
