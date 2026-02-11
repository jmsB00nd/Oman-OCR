
from typing import Dict, List, Tuple
import difflib
import re

class FraudDetectionRules:
    """Configurable rules for fraud detection in OCR corrections."""
    
    RULES = {
        'numeric_changes': {
            'enabled': True,
            'threshold': 0,
            'description': 'Changes involving numbers'
        },
        'large_changes': {
            'enabled': True,
            'threshold': 20,  # characters
            'description': 'Large text segments changed'
        },
        'keyword_changes': {
            'enabled': True,
            'keywords': ['amount', 'total', 'date', 'signature', 'name'],
            'description': 'Changes in key document fields'
        },
        'similarity_threshold': {
            'enabled': True,
            'threshold': 70,  # percent
            'description': 'Low similarity between raw and corrected'
        }
    }

def generate_fraud_report(job_data: Dict, analysis: Dict) -> str:
    """Generate comprehensive fraud detection report."""
    report = f"""
    FRAUD DETECTION REPORT
    ======================
    
    Document: {job_data['filename']}
    Processed: {job_data['timestamp']}
    Risk Level: {analysis['risk_level'].upper()}
    Risk Score: {analysis['total_risk_score']:.1f}
    
    SUMMARY
    -------
    Similarity: {analysis.get('similarity', 0):.1f}%
    Total Changes: {len(analysis.get('changes', []))}
    Suspicious Changes: {len(analysis.get('suspicious_changes', []))}
    
    VIOLATIONS
    ----------
    """
    
    for violation in analysis.get('violations', []):
        report += f"\n- {violation['rule']}: {violation['details']} ({violation['severity']})"
    
    report += f"""
    
    RAW TEXT
    --------
    {job_data.get('raw_text', 'N/A')}
    
    CORRECTED TEXT
    --------------
    {job_data.get('corrected_text', 'N/A')}
    
    RECOMMENDATION
    --------------
    {analysis.get('recommendation', 'No recommendation')}
    """
    
    return report


class TextComparator:
    """Compare raw and corrected text for fraud detection analysis."""
    
    @staticmethod
    def calculate_similarity(text1: str, text2: str) -> float:
        """Calculate similarity percentage between two texts."""
        return difflib.SequenceMatcher(None, text1, text2).ratio() * 100
    
    @staticmethod
    def word_level_diff(raw: str, corrected: str) -> List[Dict]:
        """Compare at word level and categorize changes."""
        raw_words = raw.split()
        corrected_words = corrected.split()
        
        matcher = difflib.SequenceMatcher(None, raw_words, corrected_words)
        diffs = []
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                diffs.append({
                    'type': 'replaced',
                    'raw': ' '.join(raw_words[i1:i2]),
                    'corrected': ' '.join(corrected_words[j1:j2]),
                    'position': i1
                })
            elif tag == 'delete':
                diffs.append({
                    'type': 'deleted',
                    'raw': ' '.join(raw_words[i1:i2]),
                    'corrected': '',
                    'position': i1
                })
            elif tag == 'insert':
                diffs.append({
                    'type': 'inserted',
                    'raw': '',
                    'corrected': ' '.join(corrected_words[j1:j2]),
                    'position': i1
                })
        
        return diffs
    
    @staticmethod
    def character_level_diff(raw: str, corrected: str) -> str:
        """Generate HTML with character-level highlighting."""
        diff = difflib.ndiff(raw, corrected)
        result = []
        
        for char in diff:
            if char.startswith('+ '):
                result.append(f'<span class="char-inserted">{char[2:]}</span>')
            elif char.startswith('- '):
                result.append(f'<span class="char-deleted">{char[2:]}</span>')
            elif char.startswith('  '):
                result.append(char[2:])
        
        return ''.join(result)
    
    @staticmethod
    def detect_suspicious_changes(raw: str, corrected: str, threshold: float = 30.0) -> List[Dict]:
        """Detect suspiciously large changes that might indicate fraud."""
        diffs = TextComparator.word_level_diff(raw, corrected)
        suspicious = []
        
        for diff in diffs:
            # Calculate change magnitude
            raw_len = len(diff['raw']) if diff['raw'] else 0
            corrected_len = len(diff['corrected']) if diff['corrected'] else 0
            
            # Detect numeric changes (potentially amounts)
            raw_numeric = bool(re.search(r'\d+', diff['raw']))
            corrected_numeric = bool(re.search(r'\d+', diff['corrected']))
            
            # Detect amount patterns (currency, dates, etc.)
            amount_patterns = [
                r'\d+[,.]\d{2}',  # Currency amounts
                r'\d+[/-]\d+[/-]\d+',  # Dates
                r'\b\d{4,}\b',  # Large numbers
            ]
            
            is_amount_change = any(
                re.search(pattern, diff['raw']) or re.search(pattern, diff['corrected'])
                for pattern in amount_patterns
            )
            
            # Flag if change involves numbers or is large
            if (raw_numeric or corrected_numeric or is_amount_change or 
                max(raw_len, corrected_len) > threshold):
                suspicious.append({
                    **diff,
                    'suspicion_level': 'high' if (raw_numeric and corrected_numeric) else 'medium',
                    'reason': 'numeric_change' if (raw_numeric or corrected_numeric) else 'large_change'
                })
        
        return suspicious
    
    @staticmethod
    def generate_comparison_report(raw: str, corrected: str) -> Dict:
        """Generate comprehensive comparison report."""
        return {
            'similarity_percentage': TextComparator.calculate_similarity(raw, corrected),
            'word_differences': TextComparator.word_level_diff(raw, corrected),
            'character_diff_html': TextComparator.character_level_diff(raw, corrected),
            'suspicious_changes': TextComparator.detect_suspicious_changes(raw, corrected),
            'raw_length': len(raw),
            'corrected_length': len(corrected),
            'change_ratio': abs(len(corrected) - len(raw)) / max(len(raw), 1)
        }
