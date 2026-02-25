"""
AI Analysis Module for Performance Email Notifications

This module provides AI-powered performance analysis using provider abstraction.
The LLMProvider Protocol enables easy switching between different AI providers
(Azure OpenAI, OpenAI, Anthropic, etc.) without modifying core logic.

Architecture:
- LLMProvider Protocol: Structural typing interface for all AI providers
- AzureOpenAIProvider: Concrete implementation for Azure OpenAI
- AIProviderFactory: Factory pattern for provider instantiation

Provider Abstraction Pattern:
The Protocol-based design allows dependency injection without inheritance.
Adding new providers requires only implementing the LLMProvider interface,
not modifying report_builder.py or template files.

Usage:
    # Create provider via factory
    provider = AIProviderFactory.create_provider({
        'provider_type': 'azure_openai',
        'api_key': '...',
        'endpoint': '...',
        'model': 'gpt-4o',
        'temperature': 0.0
    })

    # Generate analysis section
    analysis = provider.generate_section_analysis(
        performance_data={...},
        section_type='key_findings'
    )
"""

from typing import Dict, Any, Optional
try:
    # Python 3.8+
    from typing import Protocol, runtime_checkable
except ImportError:
    # Python 3.7 compatibility
    from typing_extensions import Protocol, runtime_checkable

from openai import AzureOpenAI, APIError, RateLimitError, APITimeoutError
import logging

logger = logging.getLogger(__name__)


@runtime_checkable
class LLMProvider(Protocol):
    """
    Protocol for AI analysis providers.

    All providers must implement this interface to be compatible
    with the AIProviderFactory and report_builder integration.

    Methods:
        generate_section_analysis: Core method for generating AI analysis sections
        check_health: Optional provider availability check
        get_model_info: Provider introspection for debugging/logging
    """

    def generate_section_analysis(
        self,
        performance_data: Dict[str, Any],
        section_type: str
    ) -> Optional[str]:
        """
        Generate analysis section from performance data.

        DEPRECATED: Use generate_analysis() instead for comprehensive single-section output.

        Args:
            performance_data: PerformanceDataContext dict with:
                - overall_metrics: System-wide metrics
                - transaction_stats: Transaction-level data
                - request_stats: Request-level data
                - sla_thresholds: Quality gate thresholds
                - test_metadata: Test identification

            section_type: One of:
                - 'key_findings': 3-5 critical issues (bullets)
                - 'performance_observations': Problematic items (table)
                - 'actionable_items': Specific recommendations (numbered)

        Returns:
            Markdown-formatted analysis string, or None on failure

        Raises:
            AIProviderError: If generation fails after retries
        """
        ...

    def generate_analysis(
        self,
        performance_data: Dict[str, Any],
        violations: Dict[str, Any],
        baseline_degradations: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Generate comprehensive AI analysis with context-aware content.

        Args:
            performance_data: PerformanceDataContext dict with:
                - overall_metrics: System-wide metrics
                - transaction_stats: Transaction-level data
                - request_stats: Request-level data
                - sla_thresholds: Quality gate thresholds with 'configured' flag
                - test_metadata: Test identification

            violations: Violation analysis dict with:
                - has_violations: bool
                - critical: list of critical violations
                - warning: list of warning violations
                - minor: list of minor violations
                - use_defaults: bool (true if using fallback thresholds)

            baseline_degradations: Optional baseline comparison dict with:
                - has_degradations: bool
                - overall: dict of overall degradations (error_rate, response_time)
                - transactions: list of transaction degradations

        Returns:
            Markdown-formatted comprehensive analysis string, or None on failure
        """
        ...

    def check_health(self) -> bool:
        """
        Verify provider availability.

        Returns:
            True if provider is accessible and functional

        Note: Used for optional health checks, not required for operation
        """
        ...

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get provider model information.

        Returns:
            Dict with keys:
                - provider: Provider name (e.g., 'azure_openai')
                - model: Model identifier (e.g., 'gpt-4o')
                - max_tokens: Context window size
                - temperature: Temperature setting
        """
        ...


class MockLLMProvider:
    """
    Mock AI provider for testing without external API calls.

    Implements LLMProvider Protocol to validate that the abstraction
    works correctly without requiring modifications to report_builder
    or templates.
    """

    def __init__(self, model: str = "mock-model", temperature: float = 0.0):
        """Initialize mock provider."""
        self.model = model
        self.temperature = temperature

    def generate_section_analysis(
        self,
        performance_data: Dict[str, Any],
        section_type: str
    ) -> Optional[str]:
        """Generate mock analysis based on section type (deprecated)."""
        if section_type == 'key_findings':
            return """- **Mock Finding 1**: Transaction POST_/api/test has 5.2% errors
- **Mock Finding 2**: Response time exceeds threshold by 15%
- **Mock Finding 3**: System performance degraded from baseline"""

        elif section_type == 'performance_observations':
            return """| Transaction | Error Rate (%) | Response Time (P95, sec) | Total Errors | Observation |
|-------------|----------------|--------------------------|--------------|-------------|
| POST_/api/test | 5.2 | 2.5 | 520 | Mock observation 1 |
| GET_/api/data | 2.1 | 1.8 | 210 | Mock observation 2 |"""

        elif section_type == 'actionable_items':
            return """1. Mock recommendation: Investigate POST_/api/test endpoint
2. Mock recommendation: Optimize GET_/api/data query performance
3. Mock recommendation: Review system resource allocation"""

        return None

    def generate_analysis(
        self,
        performance_data: Dict[str, Any],
        violations: Dict[str, Any],
        baseline_degradations: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Generate mock comprehensive analysis based on violation status."""
        if violations['has_violations']:
            return """**Test Violations Detected**

Mock analysis: Some metrics exceeded thresholds.

**Critical Violations:**
- POST_/api/test: Error rate 12.5% (threshold: 5.0%, exceeded by 7.5%)

**Recommended Actions:**
- Investigate errors in POST_/api/test endpoint"""
        else:
            sla = performance_data['sla_thresholds']
            rt_threshold = sla.get('response_time', 2000) / 1000 if sla.get('response_time') else 2.0
            er_threshold = sla.get('error_rate', 5.0) if sla.get('error_rate') else 5.0
            txn_count = len(performance_data['transaction_stats']) + len(performance_data['request_stats'])

            return f"Test completed successfully. All {txn_count} transactions within SLA thresholds (response time < {rt_threshold:.2f}s, error rate < {er_threshold:.1f}%)."

    def check_health(self) -> bool:
        """Mock health check always succeeds."""
        return True

    def get_model_info(self) -> Dict[str, Any]:
        """Return mock model information."""
        return {
            'provider': 'mock',
            'model': self.model,
            'max_tokens': 999999,
            'temperature': self.temperature
        }


class AIProviderFactory:
    """
    Factory for creating AI provider instances.

    Supports dependency injection pattern for testing and extensibility.
    """

    @staticmethod
    def create_provider(config: Dict[str, Any]) -> LLMProvider:
        """
        Create AI provider based on configuration.

        Args:
            config: Provider configuration dict with:
                - provider_type: 'azure_openai' | 'openai' | 'anthropic' | ...
                - api_key: API authentication key
                - endpoint: API endpoint URL (provider-specific)
                - api_version: API version string (provider-specific)
                - model: Model identifier
                - temperature: Temperature setting (0.0-2.0)

        Returns:
            LLMProvider instance

        Raises:
            ValueError: If provider_type is unknown
        """
        provider_type = config.get('provider_type', 'azure_openai')

        if provider_type == 'azure_openai':
            return AzureOpenAIProvider(
                api_key=config['api_key'],
                endpoint=config['endpoint'],
                api_version=config.get('api_version', '2024-02-15-preview'),
                model=config.get('model', 'gpt-4o'),
                temperature=config.get('temperature', 0.0)
            )
        elif provider_type == 'mock':
            # Mock provider for testing (no API calls)
            return MockLLMProvider(
                model=config.get('model', 'mock-model'),
                temperature=config.get('temperature', 0.0)
            )
        else:
            raise ValueError(f"Unknown AI provider type: {provider_type}")


class AzureOpenAIProvider:
    """
    Azure OpenAI implementation of LLMProvider protocol.

    Uses OpenAI Python SDK with Azure-specific configuration.
    Implements retry logic, error handling, and prompt engineering
    for performance analysis use case.
    """

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        api_version: str = "2024-02-15-preview",
        model: str = "gpt-4o",
        temperature: float = 0.0
    ):
        """
        Initialize Azure OpenAI provider.

        Args:
            api_key: Azure OpenAI API key
            endpoint: Azure OpenAI endpoint URL
            api_version: API version (default: 2024-02-15-preview)
            model: Model deployment name (default: gpt-4o)
            temperature: Temperature setting (default: 0.0 for deterministic)
        """
        self.model = model
        self.temperature = temperature
        self.client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version,
            timeout=60.0,  # 60 second timeout
            max_retries=2   # Retry transient failures up to 2 times
        )

    def _get_system_prompt(self, section_type: str) -> str:
        """
        Generate system prompt for specific analysis section type.

        Args:
            section_type: 'key_findings', 'performance_observations', or 'actionable_items'

        Returns:
            System prompt string with section-specific instructions
        """
        base_prompt = """You are a performance testing expert analyzing backend API test results.

OUTPUT REQUIREMENTS:
- Format: Valid markdown only (no HTML)
- Specificity: Always cite transaction names and actual metric values
- Focus: Prioritize errors (>5%) over slow responses
- Units: Response times in SECONDS (not milliseconds)
- Length: Maximum 500 words per section

CONSTRAINTS:
- Do NOT mention throughput in recommendations
- Do NOT make generic suggestions without data backing
- Do NOT speculate about root causes not evident in data
"""

        if section_type == 'key_findings':
            return base_prompt + """
TASK: Generate 3-5 bullet points highlighting critical performance issues.
FORMAT: - **Bold Category**: Description with transaction name and metrics
EXAMPLE: - **High Error Rate**: Transaction POST_/api/checkout has 15.2% errors (234 total)
"""
        elif section_type == 'performance_observations':
            return base_prompt + """
TASK: Create a markdown table with problematic transactions/requests (3-5 rows maximum).
COLUMNS: Transaction | Error Rate (%) | Response Time (P95, sec) | Total Errors | Observation
FORMAT: Use proper markdown table syntax with header row and separator
PRIORITY: Sort by severity - high errors first, then slow responses
"""
        elif section_type == 'actionable_items':
            return base_prompt + """
TASK: Provide 3-5 numbered, data-specific recommendations for developers/ops teams.
FORMAT: Numbered list (1. 2. 3.) with specific transaction names and metrics
EXAMPLE: 1. Investigate POST_/api/checkout endpoint - 15.2% error rate with 234 total errors suggests database connection issues
"""
        else:
            return base_prompt

    def _build_user_prompt(self, performance_data: Dict[str, Any], section_type: str) -> str:
        """
        Format performance data into structured user prompt.

        Args:
            performance_data: PerformanceDataContext dict
            section_type: Analysis section type

        Returns:
            Formatted prompt string with performance data
        """
        overall = performance_data.get('overall_metrics', {})
        transaction_stats = performance_data.get('transaction_stats', [])
        request_stats = performance_data.get('request_stats', [])
        sla_thresholds = performance_data.get('sla_thresholds', {})
        test_metadata = performance_data.get('test_metadata', {})
        context_note = performance_data.get('context_note')

        # Convert milliseconds to seconds for all response times
        overall_rt_sec = self._convert_ms_to_seconds(overall.get('response_time_95th', 0))

        prompt = f"""Analyze the following performance test results:

TEST INFORMATION:
- Test Name: {test_metadata.get('test_name', 'N/A')}
- Environment: {test_metadata.get('environment', 'N/A')}
- Status: {test_metadata.get('status', 'N/A')}
- Duration: {overall.get('duration_minutes', 0)} minutes

OVERALL METRICS:
- Response Time (P95): {overall_rt_sec:.2f}s
- Error Rate: {overall.get('error_rate', 0):.2f}%
- Total Requests: {overall.get('total_requests', 0):,}
- Total Errors: {overall.get('total_errors', 0):,}

SLA THRESHOLDS:
- Response Time: {self._convert_ms_to_seconds(sla_thresholds.get('response_time', 0)):.2f}s
- Error Rate: {sla_thresholds.get('error_rate', 0):.2f}%
"""

        # Add context note if present (e.g., missing baseline/thresholds)
        if context_note:
            prompt += f"\nIMPORTANT NOTE:\n{context_note}\n"

        # Add transaction stats if available
        if transaction_stats:
            prompt += "\nTRANSACTION PERFORMANCE (Top Problematic):\n"
            for i, txn in enumerate(transaction_stats[:10], 1):  # Limit to top 10
                txn_rt_sec = self._convert_ms_to_seconds(txn.get('response_time_95th', 0))
                prompt += f"{i}. {txn.get('name', 'Unknown')}: "
                prompt += f"RT P95={txn_rt_sec:.2f}s, "
                prompt += f"Error Rate={txn.get('error_rate', 0):.2f}%, "
                prompt += f"Total Requests={txn.get('total_requests', 0):,}, "
                prompt += f"Total Errors={txn.get('total_errors', 0):,}\n"

        # Add request stats if available
        if request_stats:
            prompt += "\nREQUEST PERFORMANCE (Top Problematic):\n"
            for i, req in enumerate(request_stats[:10], 1):  # Limit to top 10
                req_rt_sec = self._convert_ms_to_seconds(req.get('response_time_95th', 0))
                prompt += f"{i}. {req.get('name', 'Unknown')}: "
                prompt += f"RT P95={req_rt_sec:.2f}s, "
                prompt += f"Error Rate={req.get('error_rate', 0):.2f}%, "
                prompt += f"Total Requests={req.get('total_requests', 0):,}, "
                prompt += f"Total Errors={req.get('total_errors', 0):,}\n"

        prompt += f"\nGenerate {section_type.replace('_', ' ')} based on this data."

        return prompt

    @staticmethod
    def _convert_ms_to_seconds(milliseconds) -> float:
        """
        Convert milliseconds to seconds for display consistency.

        Args:
            milliseconds: Response time in milliseconds (can be string, int, or float)

        Returns:
            Response time in seconds
        """
        try:
            # Handle string inputs by converting to float first
            if isinstance(milliseconds, str):
                milliseconds = float(milliseconds)
            return float(milliseconds) / 1000.0
        except (ValueError, TypeError):
            # If conversion fails, return 0
            return 0.0

    def generate_section_analysis(
        self,
        performance_data: Dict[str, Any],
        section_type: str
    ) -> Optional[str]:
        """
        Generate section using Azure OpenAI GPT-4o.

        Implements the LLMProvider protocol method.

        Args:
            performance_data: PerformanceDataContext dict
            section_type: 'key_findings', 'performance_observations', or 'actionable_items'

        Returns:
            Markdown-formatted analysis string, or None on failure
        """
        try:
            # Build prompts
            system_prompt = self._get_system_prompt(section_type)
            user_prompt = self._build_user_prompt(performance_data, section_type)

            logger.info(f"[AIAnalyzer] Generating section: {section_type}")

            # Call Azure OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                max_tokens=1500,  # ~1000 words per section
            )

            # Extract content
            content = response.choices[0].message.content

            # Log token usage
            tokens_used = response.usage.total_tokens
            logger.info(f"[AIAnalyzer] Section {section_type} generated: {len(content)} chars, {tokens_used} tokens")

            return content

        except RateLimitError as e:
            logger.error(f"[AIAnalyzer] Rate limit error for {section_type}: {e}")
            return None

        except APITimeoutError as e:
            logger.error(f"[AIAnalyzer] Timeout error for {section_type}: {e}")
            return None

        except APIError as e:
            logger.error(f"[AIAnalyzer] API error for {section_type}: {e}")
            return None

        except Exception as e:
            logger.error(f"[AIAnalyzer] Unexpected error for {section_type}: {type(e).__name__}: {e}")
            return None

    def check_health(self) -> bool:
        """
        Check Azure OpenAI connectivity.

        Implements the LLMProvider protocol method.

        Returns:
            True if provider is accessible and functional
        """
        try:
            # Minimal test call
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5,
                temperature=0.0
            )
            return True

        except Exception as e:
            logger.error(f"[AIAnalyzer] Health check failed: {type(e).__name__}: {e}")
            return False

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get Azure OpenAI model info.

        Implements the LLMProvider protocol method.

        Returns:
            Dict with provider, model, max_tokens, temperature
        """
        return {
            'provider': 'azure_openai',
            'model': self.model,
            'max_tokens': 128000,  # GPT-4o context window
            'temperature': self.temperature
        }

    def _get_comprehensive_system_prompt(self, has_issues: bool) -> str:
        """
        Generate context-aware system prompt for comprehensive analysis.

        Args:
            has_issues: True if violations or baseline degradations detected, False if all metrics pass

        Returns:
            System prompt string with context-specific instructions
        """
        if not has_issues:
            # SUCCESS SCENARIO: Concise summary only (no violations, no baseline degradations)
            return """You are a performance testing expert analyzing SUCCESSFUL test results.

OUTPUT REQUIREMENTS:
- Format: 1-2 sentences in plain text
- Content: State that test completed successfully
- If SLA configured: mention metrics are within thresholds with values
- If baseline available: can mention performance is stable vs baseline
- If neither: just say test completed successfully with basic stats
- Example: "Test completed successfully. All 15 transactions within SLA thresholds (response time < 2.00s, error rate < 5.0%)."
- Example: "Test completed successfully with 0.0% error rate across 1,540 requests."

CRITICAL CONSTRAINTS:
- Do NOT list transactions
- Do NOT generate tables, bullet points, or sections
- Do NOT give recommendations
- Do NOT include headers like "Key Findings" or section titles
- Keep output under 100 words
"""
        else:
            # ISSUES SCENARIO: Detailed analysis (violations and/or baseline degradations)
            return """You are a performance testing expert analyzing test results WITH ISSUES (threshold violations and/or baseline degradations).

OUTPUT REQUIREMENTS:
- Format: Plain text summary + markdown recommendations
- Structure:
  1. Single paragraph (1-2 sentences): Summarize issues with actual values
  2. Blank line
  3. "**Recommendations:**" header
  4. Numbered list with 2-3 specific actions

SUMMARY FORMAT (CRITICAL):
- MUST be 1-2 sentences in paragraph form (NOT structured fields)
- Include BOTH threshold violations AND baseline degradations if present
- Example: "6 transactions exceed response time thresholds: POST_CreateCart (1.38s > 0.58s threshold), POST_Search (0.81s > 0.58s), and 4 others."
- Example: "Critical: Overall error rate is 100.00% (threshold: 5.00%, 28 errors in 28 requests), also 400% worse than baseline (25%)."
- Example: "Error rate increased 200% vs baseline (5% to 15%) and response time degraded by 50% (0.8s to 1.2s)."
- For 1-3 issues: list all with values
- For 4+ issues: list top 2-3 worst and say "and X others"

RECOMMENDATIONS FORMAT:
- Start with "**Recommendations:**" on its own line
- Numbered items (1. 2. 3.)
- Address BOTH threshold violations and baseline degradations when present
- Focus on worst offenders by name
- If 100% error rate or >50 total errors, prioritize root cause investigation
- If baseline degradation is significant (>50%), mention investigating what changed

CRITICAL CONSTRAINTS - DO NOT:
- Generate structured field lists (e.g., "Transaction Name:", "Metric Type:")
- Generate tables
- Use headers like "Violations:" or section titles
- Mention transactions that pass thresholds
- Give generic advice
- Mention throughput
- Exceed 200 words total
"""

    def _build_comprehensive_user_prompt(self, performance_data: Dict[str, Any], violations: Dict[str, Any], baseline_degradations: Optional[Dict[str, Any]] = None) -> str:
        """
        Format performance data with violation analysis and baseline degradations into comprehensive user prompt.

        Args:
            performance_data: PerformanceDataContext dict
            violations: Violation analysis dict
            baseline_degradations: Optional baseline comparison dict

        Returns:
            Formatted prompt string with performance data, violations, and baseline degradations
        """
        overall = performance_data.get('overall_metrics', {})
        sla_thresholds = performance_data.get('sla_thresholds', {})
        test_metadata = performance_data.get('test_metadata', {})
        context_note = performance_data.get('context_note')

        # Convert milliseconds to seconds
        overall_rt_sec = self._convert_ms_to_seconds(overall.get('response_time_95th', 0))
        sla_rt_sec = self._convert_ms_to_seconds(sla_thresholds.get('response_time', 0)) if sla_thresholds.get('response_time') else None

        # Build prompt
        prompt = f"""Analyze the following performance test results:

TEST INFORMATION:
- Test Name: {test_metadata.get('test_name', 'N/A')}
- Environment: {test_metadata.get('environment', 'N/A')}
- Status: {test_metadata.get('status', 'N/A')}
- Duration: {overall.get('duration_minutes', 0)} minutes

OVERALL METRICS:
- Response Time (P95): {overall_rt_sec:.2f}s
- Error Rate: {overall.get('error_rate', 0):.2f}%
- Total Requests: {overall.get('total_requests', 0):,}
- Total Errors: {overall.get('total_errors', 0):,}

"""
        # Add SLA thresholds section
        sla_configured = sla_thresholds.get('configured', False)
        if sla_configured:
            prompt += f"SLA THRESHOLDS (configured for this test):\n"
            if sla_rt_sec is not None:
                prompt += f"- Response Time: {sla_rt_sec:.2f}s\n"
            if sla_thresholds.get('error_rate') is not None:
                prompt += f"- Error Rate: {sla_thresholds.get('error_rate', 0):.2f}%\n"
        elif violations.get('use_defaults'):
            prompt += f"SLA THRESHOLDS (using defaults - no SLA configured):\n"
            if sla_rt_sec is not None:
                prompt += f"- Response Time: {sla_rt_sec:.2f}s\n"
            if sla_thresholds.get('error_rate') is not None:
                prompt += f"- Error Rate: {sla_thresholds.get('error_rate', 0):.2f}%\n"
        else:
            prompt += f"SLA THRESHOLDS: Not configured for this test\n"

        # Add baseline information
        has_baseline = baseline_degradations and baseline_degradations.get('has_degradations') is not None
        if has_baseline:
            prompt += f"BASELINE: Available for comparison\n"
        else:
            prompt += f"BASELINE: Not available or not configured\n"

        if context_note:
            prompt += f"\nIMPORTANT NOTE: {context_note}\n"

        # Add violations if they exist
        if violations['has_violations']:
            prompt += f"\n⚠️  VIOLATIONS DETECTED:\n"
            prompt += f"- Critical: {len(violations['critical'])}\n"
            prompt += f"- Warning: {len(violations['warning'])}\n"
            prompt += f"- Minor: {len(violations['minor'])}\n\n"

            # Add details for each violation (sorted by severity)
            for severity, items in [('CRITICAL', violations['critical']),
                                    ('WARNING', violations['warning']),
                                    ('MINOR', violations['minor'])]:
                if items:
                    prompt += f"{severity} VIOLATIONS:\n"
                    for v in items:
                        if v['type'] == 'error_rate':
                            prompt += f"- {v['name']}: Error rate {v['value']:.2f}% (threshold: {v['threshold']:.2f}%, exceeded by {v['exceeded_by']:.2f}%) - {v['total_errors']} errors in {v['total_requests']} requests\n"
                        elif v['type'] == 'response_time':
                            rt_sec = self._convert_ms_to_seconds(v['value'])
                            thresh_sec = self._convert_ms_to_seconds(v['threshold'])
                            exceeded_sec = self._convert_ms_to_seconds(v['exceeded_by'])
                            prompt += f"- {v['name']}: Response time {rt_sec:.2f}s (threshold: {thresh_sec:.2f}s, exceeded by {exceeded_sec:.2f}s)\n"
                    prompt += "\n"
        else:
            # Success case
            sla_configured = sla_thresholds.get('configured', False)
            has_baseline = baseline_degradations is not None

            if sla_configured:
                prompt += f"\n✅ NO VIOLATIONS: All metrics within configured SLA thresholds.\n"
            else:
                prompt += f"\n✅ Test completed successfully (no SLA configured to check violations).\n"

            if has_baseline:
                prompt += f"✅ Performance is stable vs baseline (no degradations detected).\n"

            prompt += f"Transaction count: {len(performance_data['transaction_stats']) + len(performance_data['request_stats'])}\n"

        # Add baseline degradation information
        if baseline_degradations and baseline_degradations.get('has_degradations'):
            prompt += f"\n📊 BASELINE COMPARISON (Performance vs Previous Baseline):\n"

            overall_degrade = baseline_degradations.get('overall', {})
            if overall_degrade.get('error_rate'):
                er = overall_degrade['error_rate']
                prompt += f"- Overall Error Rate: {er['current']:.2f}% vs baseline {er['baseline']:.2f}% "
                prompt += f"({er['percent_change']:.1f}% increase)\n"

            if overall_degrade.get('response_time'):
                rt = overall_degrade['response_time']
                rt_current_sec = self._convert_ms_to_seconds(rt['current'])
                rt_baseline_sec = self._convert_ms_to_seconds(rt['baseline'])
                prompt += f"- Overall Response Time: {rt_current_sec:.2f}s vs baseline {rt_baseline_sec:.2f}s "
                prompt += f"({rt['percent_change']:.1f}% slower)\n"

            txn_degrades = baseline_degradations.get('transactions', [])
            if txn_degrades:
                prompt += f"\nIndividual Transaction Degradations (>20% worse than baseline):\n"
                for txn in txn_degrades[:5]:  # Top 5
                    txn_rt_current = self._convert_ms_to_seconds(txn['current'])
                    txn_rt_baseline = self._convert_ms_to_seconds(txn['baseline'])
                    prompt += f"- {txn['name']}: {txn_rt_current:.2f}s vs baseline {txn_rt_baseline:.2f}s "
                    prompt += f"({txn['percent_change']:.1f}% slower)\n"

            prompt += "\n"

        # Add format reminder for violations or degradations
        if violations['has_violations'] or (baseline_degradations and baseline_degradations.get('has_degradations')):
            prompt += f"\nOUTPUT FORMAT REQUIREMENTS:\n"
            prompt += f"1. Write 1-2 sentence PARAGRAPH summarizing issues (threshold violations AND/OR baseline degradations)\n"
            prompt += f"   Example: '6 transactions exceed thresholds: POST_X (1.38s > 0.58s), POST_Y (0.81s > 0.58s), and 4 others.'\n"
            prompt += f"   Example: 'Critical: Error rate 100% (threshold: 5%), also 400% worse than baseline (25%).'\n"
            prompt += f"   DO NOT write: 'Transaction Name:', 'Metric Type:', etc.\n"
            prompt += f"2. Blank line\n"
            prompt += f"3. Write '**Recommendations:**' header\n"
            prompt += f"4. Write 2-3 numbered recommendations addressing BOTH threshold violations and baseline degradations if present\n"
            prompt += f"\nCRITICAL: Do NOT use field labels like 'Transaction Name:', 'Actual Value:', etc.\n"
            prompt += f"Write as natural flowing text. Maximum 200 words total.\n"

        return prompt

    def generate_analysis(
        self,
        performance_data: Dict[str, Any],
        violations: Dict[str, Any],
        baseline_degradations: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Generate single comprehensive AI analysis with context-aware content.

        Implements the LLMProvider protocol method.

        Args:
            performance_data: PerformanceDataContext dict
            violations: Violation analysis from _detect_violations()
            baseline_degradations: Optional baseline comparison from _detect_baseline_degradations()

        Returns:
            Markdown-formatted analysis string or None if error
        """
        try:
            has_violations = violations['has_violations']
            has_degradations = baseline_degradations and baseline_degradations.get('has_degradations', False)
            has_issues = has_violations or has_degradations

            system_prompt = self._get_comprehensive_system_prompt(has_issues)
            user_prompt = self._build_comprehensive_user_prompt(performance_data, violations, baseline_degradations)

            analysis_type = []
            if has_violations:
                analysis_type.append("violations")
            if has_degradations:
                analysis_type.append("baseline degradations")
            type_str = " + ".join(analysis_type) if analysis_type else "success"

            logger.info(f"[AIAnalyzer] Generating analysis with {type_str}...")

            # DEBUG: Log final prompts
            logger.info(f"[AIAnalyzer] System prompt ({len(system_prompt)} chars):")
            logger.info(f"[AIAnalyzer] {system_prompt[:500]}...")  # First 500 chars
            logger.info(f"[AIAnalyzer] User prompt ({len(user_prompt)} chars):")
            logger.info(f"[AIAnalyzer] {user_prompt}")  # Full user prompt

            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )

            content = response.choices[0].message.content.strip()
            tokens = response.usage.total_tokens if response.usage else 0

            logger.info(f"[AIAnalyzer] Analysis generated: {len(content)} chars, {tokens} tokens")

            return content

        except RateLimitError as e:
            logger.error(f"[AIAnalyzer] Rate limit error: {e}")
            return None

        except APITimeoutError as e:
            logger.error(f"[AIAnalyzer] Timeout error: {e}")
            return None

        except APIError as e:
            logger.error(f"[AIAnalyzer] API error: {e}")
            return None

        except Exception as e:
            logger.error(f"[AIAnalyzer] Unexpected error: {type(e).__name__}: {e}")
            return None
