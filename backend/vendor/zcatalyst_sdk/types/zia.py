# pylint: disable=invalid-name
from typing import List, Optional, TypedDict, Dict, Union


class ObjectParams(TypedDict):
    co_ordinates: List[int]
    object_type: str
    confidence: str


class ICatalystZiaObject(TypedDict):
    object: List[ObjectParams]


class ICatalystZiaOCR(TypedDict):
    confidence: Optional[str]
    text: str


class ICatalystZiaBarcode(TypedDict):
    content: str


class ICatalystZiaModeration(TypedDict):
    probability: Dict[str, str]
    confidence: int
    prediction: str


class ICatalystZiaCom(TypedDict):
    prediction: str
    confidence: Dict[str, str]


class FaceParams(TypedDict):
    confidence: int
    id: str
    co_ordinates: List[int]
    emotion: ICatalystZiaCom
    age: ICatalystZiaCom
    gender: ICatalystZiaCom
    landmarks: Optional[Dict[str, List[int]]]


class ICatalystZiaFace(TypedDict):
    faces: List[FaceParams]


class ICatalystZiaFaceComparison(TypedDict):
    confidence: Optional[int]
    matched: bool


class ICatalystZiaAutoML(TypedDict):
    regression_result: Optional[int]
    classification_result: Optional[Dict[str, int]]


# Text analysis response
class ConfidenceScores(TypedDict):
    negative: int
    neutral: int
    positive: int


class SentenceAnalyticsResponse(TypedDict):
    sentence: str
    sentiment: str
    confidence_scores: ConfidenceScores


class SentimentAnalysisResponseParams(TypedDict):
    sentiment: str
    sentence_analytics: List[SentenceAnalyticsResponse]
    overall_score: int
    keyword: Optional[str]


class ICatalystZiaSentimentAnalysisResponse(TypedDict):
    feature: str
    response: SentimentAnalysisResponseParams
    status: str


class ICatalystZiaSentimentAnalysis(TypedDict):
    response: List[ICatalystZiaSentimentAnalysisResponse]
    id: str
    status: str


class KeywordExtractionResponseParams(TypedDict):
    keywords: List[str]
    keyphrases: List[str]


class ICatalystZiaKeywordExtractionResponse(TypedDict):
    feature: str
    response: KeywordExtractionResponseParams
    status: str


class ICatalystZiaKeywordExtraction(TypedDict):
    response: List[ICatalystZiaKeywordExtractionResponse]
    id: str
    status: str


class GeneralEntitiesParams(TypedDict):
    NERTag: str
    start_index: int
    confidence_score: int
    end_index: int
    Token: str
    processed_value: Optional[int]


class NERPredictionResponseParams(TypedDict):
    general_entities: List[GeneralEntitiesParams]


class ICatalystZiaNERPredictonResponse(TypedDict):
    feature: str
    response: NERPredictionResponseParams
    status: str
    statusCode: int


class ICatalystZiaNERPrediction(TypedDict):
    response: List[ICatalystZiaNERPredictonResponse]
    id: str
    statusCode: int
    status: str


class ICatalystZiaTextAnalytics(TypedDict):
    response: List[Union[ICatalystZiaSentimentAnalysisResponse,
                         ICatalystZiaKeywordExtractionResponse,
                         ICatalystZiaNERPredictonResponse]]
    id: str
    status: str
