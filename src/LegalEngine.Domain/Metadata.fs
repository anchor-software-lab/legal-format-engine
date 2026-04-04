namespace LegalEngine.Domain

open System

type Party =
    { Name: string
      Role: CaptionPartyRole
      Designation: string option }

type AttorneyInfo =
    { Name: string
      BarNumber: string
      Firm: string option
      Address: string
      Phone: string
      Email: string }

type CaseMetadata =
    { CaseName: string
      CaseNumber: string
      CourtName: string
      District: string option
      CountyOfOrigin: string option
      JudgeName: string option
      Parties: Party list }

type DocumentMetadata =
    { Case: CaseMetadata
      Attorney: AttorneyInfo
      Jurisdiction: Jurisdiction
      CourtLevel: CourtLevel
      FilingType: FilingType
      DocumentTitle: string
      DateFiled: DateTime option }

module DocumentMetadata =
    let defaultWisconsin case attorney title =
        { Case = case
          Attorney = attorney
          Jurisdiction = Jurisdiction.Wisconsin
          CourtLevel = CourtLevel.Appellate
          FilingType = FilingType.AppellantBrief
          DocumentTitle = title
          DateFiled = None }
