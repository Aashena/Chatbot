/**
 * Crawl Module
 * Handles website crawling functionality including streaming updates,
 * session management, and URL discovery.
 */

export class CrawlModule {
    constructor(config) {
      this.apiBase = config.apiBase;
      this.onUrlDiscovered = config.onUrlDiscovered;
      this.onComplete = config.onComplete;
      this.onError = config.onError;
      this.updateStatus = config.updateStatus;
      this.showError = config.showError;
      this.resetInactivityTimer = config.resetInactivityTimer;
      this.clearInactivityTimer = config.clearInactivityTimer;
      
      // State
      this.currentSessionId = null;
      this.abortController = null;
      this.crawlDelay = 1.0;
      this.maxWorkers = 5;
      
      // DOM elements
      this.elements = {
        domainInput: document.getElementById('domain-input'),
        crawlBtn: document.getElementById('crawl-btn'),
        stopBtn: document.getElementById('stop-btn'),
        inlineStats: document.getElementById('crawl-inline-stats'),
        statToVisit: document.getElementById('stat-to-visit')
      };
      
      this.init();
    }
    
    /**
     * Initialize event listeners
     */
    init() {
      this.elements.crawlBtn.addEventListener('click', () => this.startCrawl());
      this.elements.stopBtn.addEventListener('click', () => this.stopCrawl());
    }
    
    /**
     * Get the current crawl configuration
     */
    getConfig() {
      return {
        crawlDelay: this.crawlDelay,
        maxWorkers: this.maxWorkers
      };
    }
    
    /**
     * Reset UI and state for a new crawl
     */
    resetState() {
      this.currentSessionId = null;
      this.elements.statToVisit.textContent = '0';
    }
    
    /**
     * Update UI for crawl start
     */
    showCrawlStartUI() {
      this.elements.crawlBtn.disabled = true;
      this.elements.stopBtn.classList.add('show');
      this.elements.inlineStats.classList.add('show');
    }
    
    /**
     * Update UI for crawl end
     */
    showCrawlEndUI() {
      this.elements.crawlBtn.disabled = false;
      this.elements.stopBtn.classList.remove('show');
    }
    
    /**
     * Handle streaming events from the crawl API
     */
    handleStreamEvent(data) {
      console.log('Stream event:', data);
      
      // Reset inactivity timer on every event
      this.resetInactivityTimer(() => {
        this.updateStatus('Connection timeout: No activity from server', 'error');
        this.showError('Connection lost: No updates received for 2 minutes');
        if (this.abortController) {
          this.abortController.abort();
        }
        this.showCrawlEndUI();
      });
      
      switch (data.type) {
        case 'session':
          this.currentSessionId = data.session_id;
          this.updateStatus(
            `${data.message}<div class="session-id">Session: ${data.session_id}</div>`,
            'info'
          );
          break;
        
        case 'config':
          this.crawlDelay = data.crawl_delay;
          this.maxWorkers = data.max_workers;
          this.updateStatus(`Crawling ${data.domain}`, 'info');
          break;
          
        case 'url':
          // Notify parent about discovered URL
          if (this.onUrlDiscovered) {
            this.onUrlDiscovered(data.url);
          }
          break;
          
        case 'progress':
          this.elements.statToVisit.textContent = data.to_visit;
          break;
        
        case 'stopped':
          this.clearInactivityTimer();
          this.updateStatus(`${data.message} (${data.total_discovered} URLs saved)`, 'success');
          this.showCrawlEndUI();
          if (this.onComplete) {
            this.onComplete({ stopped: true, totalUrls: data.total_discovered });
          }
          break;
          
        case 'complete':
          this.clearInactivityTimer();
          this.updateStatus(`${data.message} (${data.total_discovered} URLs total)`, 'success');
          this.showCrawlEndUI();
          if (this.onComplete) {
            this.onComplete({ stopped: false, totalUrls: data.total_discovered });
          }
          break;
          
        case 'error':
          if (data.url) {
            console.error(`Error with URL ${data.url}:`, data.message);
          } else {
            this.updateStatus(`Error: ${data.message}`, 'error');
          }
          break;
      }
    }
    
    /**
     * Start crawling with streaming
     */
    async startCrawl() {
      const domain = this.elements.domainInput.value.trim();
      
      if (!domain) {
        this.showError('Please enter a domain name');
        return null;
      }
      
      // Reset state
      this.resetState();
      this.showCrawlStartUI();
      this.updateStatus('Connecting to crawler...', 'info');
      
      // Create AbortController for stopping
      this.abortController = new AbortController();
      
      // Start inactivity timer
      this.resetInactivityTimer(() => {
        this.updateStatus('Connection timeout: No activity from server', 'error');
        this.showError('Connection lost: No updates received for 2 minutes');
        if (this.abortController) {
          this.abortController.abort();
        }
        this.showCrawlEndUI();
      });
      
      try {
        const response = await fetch(`${this.apiBase}/crawl/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            domain: domain
          }),
          signal: this.abortController.signal
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
            console.log('Stream complete');
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
                this.handleStreamEvent(data);
              } catch (e) {
                console.error('Error parsing event:', e, line);
              }
            }
          }
        }
        
        // Final cleanup if completed normally
        if (!this.abortController.signal.aborted) {
          this.showCrawlEndUI();
        }
        
        // Return namespace (first part of domain)
        return domain.split('/')[0];
        
      } catch (error) {
        this.clearInactivityTimer();
        if (error.name === 'AbortError') {
          console.log('Stream aborted by user');
        } else {
          console.error('Crawl error:', error);
          this.updateStatus(`Failed to crawl: ${error.message}`, 'error');
          this.showError(`Failed to crawl website: ${error.message}`);
          this.showCrawlEndUI();
          if (this.onError) {
            this.onError(error);
          }
        }
        return null;
      }
    }
    
    /**
     * Stop the current crawl session
     */
    async stopCrawl() {
      if (!this.currentSessionId) {
        this.showError('No active crawl session');
        return;
      }
      
      this.updateStatus('Stopping crawl...', 'info');
      
      try {
        // Call the stop endpoint
        const response = await fetch(`${this.apiBase}/crawl/stop/${this.currentSessionId}`, {
          method: 'POST'
        });
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        console.log('Stop response:', result);
        
        // Also abort the stream
        if (this.abortController) {
          this.abortController.abort();
        }
        
        // Clear inactivity timer
        this.clearInactivityTimer();
        
        this.updateStatus(result.message, 'success');
        this.showCrawlEndUI();
        
      } catch (error) {
        console.error('Error stopping crawl:', error);
        this.showError(`Error stopping: ${error.message}`);
      }
    }
    
    /**
     * Get the domain value
     */
    getDomain() {
      return this.elements.domainInput.value.trim();
    }
    
    /**
     * Check if a crawl is currently active
     */
    isActive() {
      return this.currentSessionId !== null && this.abortController !== null;
    }
  }