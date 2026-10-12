SP_Desk

Aplicação Python que transmite a tela do computador para um dispositivo móvel via navegador, com suporte a interação por toque e monitoramento de hardware (CPU, RAM e GPU).

Requisitos
Python 3.10+
Android com depuração USB ativada (para conexão via USB)
ADB instalado no computador (para conexão via USB)
Instalação

Instale as dependências:

pip install -r requirements.txt

Como executar

Inicie a aplicação:

python sp_desk.py


Escolha o modo desejado no terminal:

1 — Tela com touch: transmite a tela do computador e permite controlá-lo pelo dispositivo móvel.
2 — Painel de hardware: exibe métricas de CPU, RAM e GPU, quando disponíveis.
Acesso pelo dispositivo

Via rede Wi-Fi: acesse http://IP_DO_PC:5000 no navegador do dispositivo, utilizando o IP local do computador.

Via USB (Android):

Conecte o dispositivo ao computador por USB e habilite a depuração USB.
Confirme que o ADB reconhece o dispositivo:
   adb devices

Configure o redirecionamento da porta:
   adb reverse tcp:5000 tcp:5000

Abra no navegador do dispositivo:
   http://localhost:5000


O comando adb reverse permite acessar o servidor do computador pelo dispositivo Android através da conexão USB, sem precisar utilizar o IP local do computador.

Observações
A porta padrão da aplicação é 5000.
O modo de tela utiliza captura de vídeo e WebSocket para transmitir as imagens em tempo real.
O controle por toque simula movimentos e cliques do mouse no computador.
As métricas de GPU dependem da disponibilidade de ferramentas e drivers compatíveis.
A aplicação não possui autenticação implementada. Utilize apenas em ambientes confiáveis e não exponha o servidor diretamente à internet.