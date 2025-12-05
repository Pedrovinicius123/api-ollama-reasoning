"""
Thread Manager - Gerenciador de Threads para Processamento Assíncrono

Este módulo fornece uma classe que gerencia a execução segura de threads
para tarefas de longa duração (raciocínio profundo, geração de artigos).

Funcionalidade:
- Monitora uma fila de threads de forma thread-safe
- Inicia threads automaticamente quando adicionadas
- Remove threads completadas da fila
- Evita tentativas de reiniciar threads já iniciadas

Uso:
    manager = ThreadManager()
    manager.start()
    
    # Em outro lugar da aplicação
    t = threading.Thread(target=minha_funcao, args=(args,))
    with manager.lock:
        manager.threads.append(t)
"""

import threading
import time


class ThreadManager(threading.Thread):
    """
    Gerenciador de threads para execução de tarefas assíncrona.
    
    Esta classe executa como uma thread daemon que continuamente monitora
    uma fila de threads a serem executadas e as inicia conforme adicionadas.
    
    Utiliza um lock (mutex) para garantir operações thread-safe na fila.
    
    Attributes:
        threads (list): Lista de objetos threading.Thread a serem executados
        daemon (bool): Se True, a thread é encerrada quando a aplicação principal sai
        lock (threading.Lock): Mutex para operações thread-safe na fila
    
    Methods:
        run(): Loop principal que monitora e inicia threads
        
    Exemplo:
        >>> manager = ThreadManager()
        >>> manager.start()  # Inicia o gerenciador em background
        >>> 
        >>> # Adicionar uma tarefa
        >>> def minha_tarefa():
        ...     print("Executando tarefa")
        >>> 
        >>> t = threading.Thread(target=minha_tarefa)
        >>> with manager.lock:
        ...     manager.threads.append(t)
    """
    
    def __init__(self):
        """
        Inicializa o ThreadManager.
        
        Cria:
        - Uma lista vazia de threads a gerenciar
        - Um lock para sincronização thread-safe
        - Define como thread daemon (para não bloquear encerramento da app)
        """
        threading.Thread.__init__(self)
        self.threads = []
        self.daemon = True  # Thread daemon encerra quando app principal encerra
        self.lock = threading.Lock()

    def run(self):
        """
        Loop principal do gerenciador de threads.
        
        Continuamente:
        1. Verifica cada thread na fila
        2. Se não foi iniciada ainda, inicia a thread
        3. Se foi iniciada e completou, remove da fila
        4. Se ocorrer RuntimeError (thread já iniciada), remove da fila
        
        O loop continua indefinidamente (é uma thread daemon).
        
        Operações:
        - Tenta iniciar cada thread com thread.start()
        - RuntimeError indica que thread já foi iniciada
        - Verifica com thread.is_alive() se thread completou
        - Remove thread completada de forma thread-safe
        
        Comportamento:
        - Não bloqueia, verifica continuamente
        - Operações sobre self.threads sempre feitas com lock
        - Permite que múltiplas threads sejam adicionadas/removidas
        
        Nota:
        - Este loop não tem sleep(), considera usar para economia de CPU
        - Em produção, considerar adicionar time.sleep(0.1) para reduzir CPU
        """
        # Loop infinito - continua enquanto a aplicação estiver rodando
        while True:
            to_start = None
            
            # Acesso thread-safe à lista de threads
            for thread in self.threads:
                try:
                    with self.lock:
                       # Tenta iniciar a thread
                       # RuntimeError é levantado se já foi iniciada
                       thread.start()
                except RuntimeError:
                    # Thread já foi iniciada anteriormente
                    # Se completou, remove da fila
                    with self.lock:
                        if not thread.is_alive():
                            thread.join()
                            self.threads.remove(thread)
