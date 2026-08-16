export interface CitedClaim {
  claim: string;
  citation: string;
  confidence: number;
}

export interface MedicalAnswer {
  answer: string;
  claims: CitedClaim[];
  disclaimer: string;
}

export interface RequestOutput {
  status: 'medical_agent' | 'conversational_agent' | 'escalated' | string;
  medical_output?: MedicalAnswer | null;
  conversational_output?: string | null;
  feedback?: string | null;
  groundness_verdict?: 'claim_is_tracable' | 'claim_not_tracable' | string | null;
  retrieved_chunks?: string[];
  retry_count?: number;
}
