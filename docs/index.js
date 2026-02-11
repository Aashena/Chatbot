/**
 * Index Module
 * Handles URL indexing functionality including streaming updates,
 * batch processing, and progress tracking.
 */

export class IndexModule {
    constructor(config) {
      this.apiBase = config.apiBase;
      this.onComplete = config.onComplete;
      this.onError = config.onError;
      this.updateStatus = config.updateStatus;
      this.showError = config.showError;
      this.showSuccess = config.showSuccess;
      this.resetInactivityTimer = config.resetInactivityTimer;
      this.clearInactivityTimer = config.clearInactivityTimer;
      this.getCurrentUrls = config.getCurrentUrls;
      
      // State
      this.namespace = null;
      this.crawlDelay = 1.0;
      this.maxWorkers = 5;
      
      // DOM elements
      this.elements = {
        processBtn: document.getElementById('process-btn'),
        indexInlineStats: document.getElementById('index-inline-stats'),
        statBatch: document.getElementById('stat-batch'),
        statUrlsProcessed: document.getElementById('stat-urls-processed'),
        statChunks: document.getElementById('stat-chunks')
      };
      
      this.init();
    }
    
    /**
     * Initialize event listeners
     */
    init() {
      this.elements.processBtn.addEventListener('click', () => this.startIndexing());
    }
    
    /**
     * Set the namespace and crawl configuration
     */
    setConfig(namespace, crawlConfig) {
      this.namespace = namespace;
      if (crawlConfig) {
        this.crawlDelay = crawlConfig.crawlDelay || 1.0;
        this.maxWorkers = crawlConfig.maxWorkers || 5;
      }
    }
    
    /**
     * Reset stats display
     */
    resetStats() {
      this.elements.statBatch.textContent = '0/0';
      this.elements.statUrlsProcessed.textContent = '0';
      this.elements.statChunks.textContent = '0';
    }
    
    /**
     * Update UI for indexing start
     */
    showIndexStartUI() {
      this.elements.processBtn.disabled = true;
      this.elements.indexInlineStats.classList.add('show');
    }
    
    /**
     * Update UI for indexing end
     */
    showIndexEndUI() {
      this.elements.processBtn.disabled = false;
    }
    
    /**
     * Handle streaming events from the index API
     */
    handleIndexEvent(data) {
      console.log('Index event:', data);
      
      // Reset inactivity timer on every event
      this.resetInactivityTimer(() => {
        this.updateStatus('Connection timeout: No activity from server', 'error', 'index-status');
        this.showError('Connection lost: No updates received for 2 minutes');
        this.showIndexEndUI();
      });
      
      switch (data.type) {
        case 'start':
          this.elements.indexInlineStats.classList.add('show');
          this.updateStatus(
            `Starting indexing of ${data.total_urls} URLs...`,
            'info',
            'index-status'
          );
          document.getElementById('index-status')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          break;
        
        case 'existing_check':
          this.updateStatus(
            `Checking existing URLs... Found ${data.existing_count} already indexed`, 
            'info', 
            'index-status'
          );
          break;
        
        case 'filter_complete':
          this.updateStatus(
            `${data.message}`,
            'info',
            'index-status'
          );
          break;
        
        case 'batch_start':
          this.elements.statBatch.textContent = `${data.batch_number}/${data.total_batches}`;
          this.updateStatus(
            `Processing batch ${data.batch_number} of ${data.total_batches} (${data.batch_size} URLs)`,
            'info',
            'index-status'
          );
          break;
        
        case 'docs_loaded':
          this.updateStatus(
            `Loaded ${data.docs_count} documents from batch ${data.batch_number}`,
            'info',
            'index-status'
          );
          break;
        
        case 'chunking_complete':
          this.updateStatus(
            `Created ${data.chunks_before_dedup} chunks, removing duplicates...`,
            'info',
            'index-status'
          );
          break;
        
        case 'deduplication_complete':
          this.updateStatus(
            `Deduplication complete: ${data.unique_chunks} unique chunks`,
            'info',
            'index-status'
          );
          break;
        
        case 'batch_complete':
          this.elements.statChunks.textContent = data.total_chunks_so_far;
          this.updateStatus(
            `Batch ${data.batch_number}/${data.total_batches} complete: ${data.batch_chunks} chunks indexed`,
            'info',
            'index-status'
          );
          break;
        
        case 'complete':
          this.clearInactivityTimer();
          this.elements.statChunks.textContent = data.total_chunks;
          this.elements.statUrlsProcessed.textContent = data.urls_processed;
          this.updateStatus(
            `✓ Indexing complete! ${data.total_chunks} chunks from ${data.urls_processed} URLs`,
            'success',
            'index-status'
          );
          this.showSuccess(
            `✓ Successfully indexed ${data.urls_processed} URLs into ${data.total_chunks} chunks!`
          );
          document.getElementById('index-status')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          
          if (this.onComplete) {
            this.onComplete({
              totalChunks: data.total_chunks,
              urlsProcessed: data.urls_processed,
              namespace: this.namespace
            });
          }
          break;
        
        case 'batch_error':
          this.updateStatus(
            `Error in batch ${data.batch_number}: ${data.message}`,
            'error',
            'index-status'
          );
          break;
        
        case 'error':
          this.clearInactivityTimer();
          this.updateStatus(`Error: ${data.message}`, 'error', 'index-status');
          this.showError(`Indexing error: ${data.message}`);
          if (this.onError) {
            this.onError(new Error(data.message));
          }
          break;
      }
    }
    
    /**
     * Start indexing URLs with streaming
     */
    async startIndexing() {
      // Get URLs from the main app (via callback)
      const urls = this.getCurrentUrls();
      
      if (urls.length === 0) {
        this.showError('No URLs to process');
        return;
      }
      
      if (!this.namespace) {
        this.showError('No namespace set. Please crawl a domain first.');
        return;
      }
      
      // Reset and show UI
      this.resetStats();
      this.showIndexStartUI();
      
      // Start inactivity timer
      this.resetInactivityTimer(() => {
        this.updateStatus('Connection timeout: No activity from server', 'error', 'index-status');
        this.showError('Connection lost: No updates received for 2 minutes');
        this.showIndexEndUI();
      });
      
      try {
        const response = await fetch(`${this.apiBase}/index/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            urls: urls,
            namespace: this.namespace,
            delay: this.crawlDelay,
            max_workers: this.maxWorkers
          })
        });
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        
        while (true) {
          const { done, value } = await reader.read();
          
          if (done) {
            console.log('Index stream complete');
            this.clearInactivityTimer();
            break;
          }
          
          // Decode and add to buffer
          buffer += decoder.decode(value, { stream: true });
          
          // Process complete lines
          const lines = buffer.split('\n');
          buffer = lines.pop(); // Keep incomplete line in buffer
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                this.handleIndexEvent(data);
              } catch (e) {
                console.error('Error parsing index event:', e, line);
              }
            }
          }
        }
        
      } catch (error) {
        this.clearInactivityTimer();
        console.error('Index error:', error);
        this.showError(`Failed to index URLs: ${error.message}`);
        this.updateStatus(`Error: ${error.message}`, 'error', 'index-status');
        if (this.onError) {
          this.onError(error);
        }
      } finally {
        this.showIndexEndUI();
      }
    }
    
    /**
     * Enable or disable the process button
     */
    setEnabled(enabled) {
      this.elements.processBtn.disabled = !enabled;
    }
    
    /**
     * Check if indexing is currently active
     */
    isActive() {
      return this.elements.processBtn.disabled;
    }
  }