import logging
from pydantic import BaseModel, Field
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from vc_vetter.config import Settings

try:
    from langchain_ollama import ChatOllama
except ImportError:
    # Fallback to langchain_community if langchain_ollama is not available
    from langchain_community.chat_models import ChatOllama

logger = logging.getLogger(__name__)

class VettingDecision(BaseModel):
    """The structured decision output returned by the vetting agent."""
    is_fit: bool = Field(description="True if the VC's focus matches the startup's profile, False otherwise.")
    reasoning: str = Field(description="A concise, one-sentence justification detailing why they are or are not a match.")

class VCVetter:
    """Class wrapper around LLM vetting operations using LangChain."""
    
    def __init__(self, settings: Settings = None, llm: ChatOllama = None):
        self.settings = settings or Settings()
        
        # Accept a shared LLM instance to optimize memory and processing time in parallel threads
        if llm is not None:
            self.llm = llm
        else:
            self.llm = ChatOllama(model=self.settings.local_llm_model, temperature=0.0)

        self.parser = PydanticOutputParser(pydantic_object=VettingDecision)
        
        self.prompt = PromptTemplate(
            template=(
                "You are an expert VC analyst determining if a venture capital fund is a good fit for a startup.\n\n"
                "{format_instructions}\n\n"
                "**Startup Profile:**\n"
                "{startup_details}\n\n"
                "**Scraped Website Content from the VC:**\n"
                "---\n"
                "{website_content}\n"
                "---\n\n"
                "Review the VC's investment stage, focus industries, and target geographic regions to determine if they align "
                "with the startup's profile. Respond strictly in the JSON format requested."
            ),
            input_variables=["startup_details", "website_content"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        
        self.chain = self.prompt | self.llm | self.parser

    def analyze_fit(self, website_text: str, startup_info: str) -> VettingDecision:
        """Uses local LLM to analyze the fit of a VC with the startup profile.
        
        Args:
            website_text: Extracted text from the VC website.
            startup_info: Details of the startup's product, stage, size, and raise amount.
            
        Returns:
            VettingDecision: A validated Pydantic model with the outcome and reasoning.
        """
        if not website_text or website_text.isspace():
            return VettingDecision(
                is_fit=False, 
                reasoning="Could not scrape any meaningful text from the website."
            )
            
        try:
            return self.chain.invoke({
                "startup_details": startup_info,
                "website_content": website_text
            })
        except Exception as e:
            logger.error(f"Error during LLM analysis: {e}")
            return VettingDecision(
                is_fit=False,
                reasoning=f"LLM analysis failed: {str(e)}"
            )
