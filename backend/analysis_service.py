```python
"""
BiasLens Analysis Service
Provides NLP analysis for bias detection and sentiment scoring in job descriptions
and candidate screening patterns.
"""

import re
from typing import Dict, List, Tuple, Optional, Any
from collections import Counter
import logging

import spacy
from spacy.tokens import Doc
import pandas as pd
from textblob import TextBlob

logger = logging.getLogger(__name__)


class BiasAnalysisService:
    """
    Service for analyzing text content for unconscious bias indicators,
    gendered language, and sentiment analysis.
    """

    # Gendered terms that may indicate bias
    MASCULINE_CODED_WORDS = {
        'aggressive', 'ambitious', 'analytical', 'assertive', 'athletic',
        'autonomous', 'battle', 'boast', 'challenge', 'champion', 'competitive',
        'confident', 'courageous', '决心', 'decisive', 'defend', 'determined',
        'dominant', 'driven', 'fearless', 'force', 'grenade', 'headstrong',
        'hierarchical', 'hostile', 'impulsive', 'independent', 'individual',
        'intellectual', 'lead', 'logic', 'objective', 'opinion', 'outspoken',
        'persist', 'principle', 'reckless', 'self-confident', 'self-reliant',
        'self-sufficient', 'selfreliant', 'stubborn', 'superior', 'unreasonable'
    }

    FEMININE_CODED_WORDS = {
        'affectionate', 'agreeable', 'cheer', 'child', 'collaborate',
        'collab', 'commitment', 'communal', 'compassion', 'connect',
        'considerate', 'cooperate', 'cooperative', 'commit', 'depend',
        'devoted', 'emotional', 'empathetic', 'empathy', 'flatterable',
        'gentle', 'honest', 'interpersonal', 'interdependent', 'kinship',
        'loyal', 'modesty', 'nag', 'nurture', 'pleasant', 'polite',
        'quiet', 'responsive', 'sensitive', 'submissive', 'support',
        'supportive', 'sympathy', 'tender', 'together', 'trust', 'understand',
        'warm', 'whin', 'yield'
    }

    # Age-related bias indicators
    AGE_BIAS_TERMS = {
        'young', 'energetic', 'digital native', 'recent graduate',
        'enthusiastic', 'fresh', 'dynamic', 'vibrant', 'tech-savvy',
        'generation', 'millennial', 'gen z'
    }

    # Exclusionary or potentially biased phrases
    EXCLUSIONARY_PHRASES = [
        r'native\s+english\s+speaker',
        r'culture\s+fit',
        r'work\s+hard\s*[,/]\s*play\s+hard',
        r'fast[\s-]paced\s+environment',
        r'ninja|rockstar|guru|wizard',
        r'recent\s+college\s+graduate',
        r'years?\s+young',
        r'must\s+be\s+available\s+(evenings|weekends)',
    ]

    # Required qualifications that may be unnecessarily restrictive
    OVERLY_RESTRICTIVE_TERMS = {
        'expert', 'master', 'years of experience', 'extensive experience',
        'proven track record', 'must have', 'required'
    }

    def __init__(self):
        """Initialize the analysis service with spaCy model."""
        try:
            self.nlp = spacy.load('en_core_web_sm')
            logger.info("spaCy model loaded successfully")
        except OSError:
            logger.error("spaCy model 'en_core_web_sm' not found. Run: python -m spacy download en_core_web_sm")
            raise

    def analyze_job_description(self, text: str) -> Dict[str, Any]:
        """
        Perform comprehensive bias analysis on a job description.

        Args:
            text: The job description text to analyze

        Returns:
            Dictionary containing analysis results including bias scores,
            flagged terms, sentiment analysis, and recommendations
        """
        if not text or not text.strip():
            raise ValueError("Job description text cannot be empty")

        try:
            doc = self.nlp(text.lower())
            
            # Run various analysis components
            gender_bias = self._analyze_gender_bias(doc, text.lower())
            age_bias = self._analyze_age_bias(doc, text.lower())
            exclusionary = self._analyze_exclusionary_language(text.lower())
            restrictive = self._analyze_restrictiveness(text.lower())
            sentiment = self._analyze_sentiment(text)
            readability = self._analyze_readability(text)
            
            # Calculate overall bias score (0-100, lower is better)
            overall_score = self._calculate_overall_bias_score(
                gender_bias, age_bias, exclusionary, restrictive
            )
            
            # Generate actionable recommendations
            recommendations = self._generate_recommendations(
                gender_bias, age_bias, exclusionary, restrictive
            )
            
            return {
                'overall_bias_score': overall_score,
                'gender_bias': gender_bias,
                'age_bias': age_bias,
                'exclusionary_language': exclusionary,
                'restrictiveness': restrictive,
                'sentiment': sentiment,
                'readability': readability,
                'recommendations': recommendations,
                'word_count': len(doc),
                'sentence_count': len(list(doc.sents))
            }
            
        except Exception as e:
            logger.error(f"Error analyzing job description: {str(e)}")
            raise

    def _analyze_gender_bias(self, doc: Doc, text: str) -> Dict[str, Any]:
        """
        Analyze text for gendered language that may discourage applicants.

        Args:
            doc: Processed spaCy document
            text: Original lowercase text

        Returns:
            Dictionary with masculine/feminine coded words and bias ratio
        """
        masculine_found = []
        feminine_found = []
        
        for token in doc:
            token_text = token.text
            if token_text in self.MASCULINE_CODED_WORDS:
                masculine_found.append(token_text)
            elif token_text in self.FEMININE_CODED_WORDS:
                feminine_found.append(token_text)
        
        # Calculate coding ratio (positive = masculine-coded, negative = feminine-coded)
        total = len(masculine_found) + len(feminine_found)
        coding_ratio = 0.0
        
        if total > 0:
            coding_ratio = (len(masculine_found) - len(feminine_found)) / total
        
        # Determine bias level
        bias_level = self._get_bias_level(abs(coding_ratio))
        
        return {
            'masculine_coded_words': list(set(masculine_found)),
            'feminine_coded_words': list(set(feminine_found)),
            'masculine_count': len(masculine_found),
            'feminine_count': len(feminine_found),
            'coding_ratio': round(coding_ratio, 3),
            'bias_level': bias_level,
            'has_bias': abs(coding_ratio) > 0.3 or total > 8
        }

    def _analyze_age_bias(self, doc: Doc, text: str) -> Dict[str, Any]:
        """
        Detect age-related bias indicators in the text.

        Args:
            doc: Processed spaCy document
            text: Original lowercase text

        Returns:
            Dictionary with flagged age-related terms and bias indicators
        """
        age_terms_found = []
        
        for token in doc:
            if token.text in self.AGE_BIAS_TERMS:
                age_terms_found.append(token.text)
        
        # Check for specific problematic phrases
        problematic_phrases = []
        if 'digital native' in text:
            problematic_phrases.append('digital native')
        if re.search(r'\d+\s*years?\s+young', text):
            problematic_phrases.append('years young')
        
        has_bias = len(age_terms_found) > 2 or len(problematic_phrases) > 0
        
        return {
            'flagged_terms': list(set(age_terms_found)),
            'problematic_phrases': problematic_phrases,
            'count': len(age_terms_found),
            'has_bias': has_bias,
            'severity': 'high' if problematic_phrases else ('medium' if len(age_terms_found) > 3 else 'low')
        }

    def _analyze_exclusionary_language(self, text: str) -> Dict[str, Any]:
        """
        Identify exclusionary phrases that may deter diverse candidates.

        Args:
            text: Lowercase job description text

        Returns:
            Dictionary with found exclusionary phrases and examples
        """
        found_patterns = []
        
        for pattern in self.EXCLUSIONARY_PHRASES:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                found_patterns.append({
                    'phrase': match.group(0),
                    'pattern': pattern,
                    'position': match.start()
                })
        
        return {
            'found_patterns': found_patterns,
            'count': len(found_patterns),
            'has_exclusionary_language': len(found_patterns) > 0,
            'severity': 'high' if len(found_patterns) > 2 else ('medium' if len(found_patterns) > 0 else 'low')
        }

    def _analyze_restrictiveness(self, text: str) -> Dict[str, Any]:
        """
        Analyze how restrictive the requirements are, which may unnecessarily
        limit the candidate pool.

        Args:
            text: Lowercase job description text

        Returns:
            Dictionary with restrictiveness metrics
        """
        restrictive_terms_found = []
        
        for term in self.OVERLY_RESTRICTIVE_TERMS:
            if term in text:
                count = text.count(term)
                restrictive_terms_found.extend([term] * count)
        
        # Count instances of "must", "required", "mandatory"
        must_count = len(re.findall(r'\bmust\b', text))
        required_count = len(re.findall(r'\brequired\b', text))
        mandatory_count = len(re.findall(r'\bmandatory\b', text))
        
        total_restrictive = len(restrictive_terms_found) + must_count + required_count + mandatory_count
        
        # Assess restrictiveness level
        if total_restrictive > 10:
            level = 'very_high'
        elif total_restrictive > 6:
            level = 'high'
        elif total_restrictive > 3:
            level = 'moderate'
        else:
            level = 'low'
        
        return {
            'restrictive_terms': list(set(restrictive_terms_found)),
            'must_count': must_count,
            'required_count': required_count,
            'mandatory_count': mandatory_count,
            'total_count': total_restrictive,
            'restrictiveness_level': level,
            'is_overly_restrictive': total_restrictive > 6
        }

    def _analyze_sentiment(self, text: str) -> Dict[str, float]:
        """
        Analyze the overall sentiment and tone of the job description.

        Args:
            text: Job description text

        Returns:
            Dictionary with sentiment polarity and subjectivity scores
        """
        blob = TextBlob(text)
        
        # Polarity: -1 (negative) to 1 (