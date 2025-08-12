class DomainError(Exception):
    pass

class NoDatasetError(DomainError):
    pass

class EmptyTableError(DomainError):
    pass

class InvalidQuestionError(DomainError):
    pass
