# Generated from SMILE_Generalized.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .SMILE_GeneralizedParser import SMILE_GeneralizedParser
else:
    from SMILE_GeneralizedParser import SMILE_GeneralizedParser

# This class defines a complete listener for a parse tree produced by SMILE_GeneralizedParser.
class SMILE_GeneralizedListener(ParseTreeListener):

    # Enter a parse tree produced by SMILE_GeneralizedParser#migration.
    def enterMigration(self, ctx:SMILE_GeneralizedParser.MigrationContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#migration.
    def exitMigration(self, ctx:SMILE_GeneralizedParser.MigrationContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#header.
    def enterHeader(self, ctx:SMILE_GeneralizedParser.HeaderContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#header.
    def exitHeader(self, ctx:SMILE_GeneralizedParser.HeaderContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#migrationDecl.
    def enterMigrationDecl(self, ctx:SMILE_GeneralizedParser.MigrationDeclContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#migrationDecl.
    def exitMigrationDecl(self, ctx:SMILE_GeneralizedParser.MigrationDeclContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#evolutionDecl.
    def enterEvolutionDecl(self, ctx:SMILE_GeneralizedParser.EvolutionDeclContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#evolutionDecl.
    def exitEvolutionDecl(self, ctx:SMILE_GeneralizedParser.EvolutionDeclContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#fromToDecl.
    def enterFromToDecl(self, ctx:SMILE_GeneralizedParser.FromToDeclContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#fromToDecl.
    def exitFromToDecl(self, ctx:SMILE_GeneralizedParser.FromToDeclContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#usingDecl.
    def enterUsingDecl(self, ctx:SMILE_GeneralizedParser.UsingDeclContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#usingDecl.
    def exitUsingDecl(self, ctx:SMILE_GeneralizedParser.UsingDeclContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#databaseType.
    def enterDatabaseType(self, ctx:SMILE_GeneralizedParser.DatabaseTypeContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#databaseType.
    def exitDatabaseType(self, ctx:SMILE_GeneralizedParser.DatabaseTypeContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#version.
    def enterVersion(self, ctx:SMILE_GeneralizedParser.VersionContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#version.
    def exitVersion(self, ctx:SMILE_GeneralizedParser.VersionContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#operation.
    def enterOperation(self, ctx:SMILE_GeneralizedParser.OperationContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#operation.
    def exitOperation(self, ctx:SMILE_GeneralizedParser.OperationContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#add_gen.
    def enterAdd_gen(self, ctx:SMILE_GeneralizedParser.Add_genContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#add_gen.
    def exitAdd_gen(self, ctx:SMILE_GeneralizedParser.Add_genContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#propertyAdd.
    def enterPropertyAdd(self, ctx:SMILE_GeneralizedParser.PropertyAddContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#propertyAdd.
    def exitPropertyAdd(self, ctx:SMILE_GeneralizedParser.PropertyAddContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#propertyClause.
    def enterPropertyClause(self, ctx:SMILE_GeneralizedParser.PropertyClauseContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#propertyClause.
    def exitPropertyClause(self, ctx:SMILE_GeneralizedParser.PropertyClauseContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#withTypeClause.
    def enterWithTypeClause(self, ctx:SMILE_GeneralizedParser.WithTypeClauseContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#withTypeClause.
    def exitWithTypeClause(self, ctx:SMILE_GeneralizedParser.WithTypeClauseContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#withDefaultClause.
    def enterWithDefaultClause(self, ctx:SMILE_GeneralizedParser.WithDefaultClauseContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#withDefaultClause.
    def exitWithDefaultClause(self, ctx:SMILE_GeneralizedParser.WithDefaultClauseContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#notNullClause.
    def enterNotNullClause(self, ctx:SMILE_GeneralizedParser.NotNullClauseContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#notNullClause.
    def exitNotNullClause(self, ctx:SMILE_GeneralizedParser.NotNullClauseContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#foreignKeyAdd.
    def enterForeignKeyAdd(self, ctx:SMILE_GeneralizedParser.ForeignKeyAddContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#foreignKeyAdd.
    def exitForeignKeyAdd(self, ctx:SMILE_GeneralizedParser.ForeignKeyAddContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#constraintClause.
    def enterConstraintClause(self, ctx:SMILE_GeneralizedParser.ConstraintClauseContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#constraintClause.
    def exitConstraintClause(self, ctx:SMILE_GeneralizedParser.ConstraintClauseContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#embeddedAdd.
    def enterEmbeddedAdd(self, ctx:SMILE_GeneralizedParser.EmbeddedAddContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#embeddedAdd.
    def exitEmbeddedAdd(self, ctx:SMILE_GeneralizedParser.EmbeddedAddContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#embeddedClause.
    def enterEmbeddedClause(self, ctx:SMILE_GeneralizedParser.EmbeddedClauseContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#embeddedClause.
    def exitEmbeddedClause(self, ctx:SMILE_GeneralizedParser.EmbeddedClauseContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#withStructureClause.
    def enterWithStructureClause(self, ctx:SMILE_GeneralizedParser.WithStructureClauseContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#withStructureClause.
    def exitWithStructureClause(self, ctx:SMILE_GeneralizedParser.WithStructureClauseContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#entityAdd.
    def enterEntityAdd(self, ctx:SMILE_GeneralizedParser.EntityAddContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#entityAdd.
    def exitEntityAdd(self, ctx:SMILE_GeneralizedParser.EntityAddContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#entityClause.
    def enterEntityClause(self, ctx:SMILE_GeneralizedParser.EntityClauseContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#entityClause.
    def exitEntityClause(self, ctx:SMILE_GeneralizedParser.EntityClauseContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#withKeyClause.
    def enterWithKeyClause(self, ctx:SMILE_GeneralizedParser.WithKeyClauseContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#withKeyClause.
    def exitWithKeyClause(self, ctx:SMILE_GeneralizedParser.WithKeyClauseContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#keyAdd.
    def enterKeyAdd(self, ctx:SMILE_GeneralizedParser.KeyAddContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#keyAdd.
    def exitKeyAdd(self, ctx:SMILE_GeneralizedParser.KeyAddContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#keyColumns.
    def enterKeyColumns(self, ctx:SMILE_GeneralizedParser.KeyColumnsContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#keyColumns.
    def exitKeyColumns(self, ctx:SMILE_GeneralizedParser.KeyColumnsContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#labelAdd.
    def enterLabelAdd(self, ctx:SMILE_GeneralizedParser.LabelAddContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#labelAdd.
    def exitLabelAdd(self, ctx:SMILE_GeneralizedParser.LabelAddContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#constraintAdd.
    def enterConstraintAdd(self, ctx:SMILE_GeneralizedParser.ConstraintAddContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#constraintAdd.
    def exitConstraintAdd(self, ctx:SMILE_GeneralizedParser.ConstraintAddContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#ConstraintBodyReference.
    def enterConstraintBodyReference(self, ctx:SMILE_GeneralizedParser.ConstraintBodyReferenceContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#ConstraintBodyReference.
    def exitConstraintBodyReference(self, ctx:SMILE_GeneralizedParser.ConstraintBodyReferenceContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#ConstraintBodyCheck.
    def enterConstraintBodyCheck(self, ctx:SMILE_GeneralizedParser.ConstraintBodyCheckContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#ConstraintBodyCheck.
    def exitConstraintBodyCheck(self, ctx:SMILE_GeneralizedParser.ConstraintBodyCheckContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#ConstraintBodyExistence.
    def enterConstraintBodyExistence(self, ctx:SMILE_GeneralizedParser.ConstraintBodyExistenceContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#ConstraintBodyExistence.
    def exitConstraintBodyExistence(self, ctx:SMILE_GeneralizedParser.ConstraintBodyExistenceContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#CheckParenExpr.
    def enterCheckParenExpr(self, ctx:SMILE_GeneralizedParser.CheckParenExprContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#CheckParenExpr.
    def exitCheckParenExpr(self, ctx:SMILE_GeneralizedParser.CheckParenExprContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#CheckAtomExpr.
    def enterCheckAtomExpr(self, ctx:SMILE_GeneralizedParser.CheckAtomExprContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#CheckAtomExpr.
    def exitCheckAtomExpr(self, ctx:SMILE_GeneralizedParser.CheckAtomExprContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#CheckAndExpr.
    def enterCheckAndExpr(self, ctx:SMILE_GeneralizedParser.CheckAndExprContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#CheckAndExpr.
    def exitCheckAndExpr(self, ctx:SMILE_GeneralizedParser.CheckAndExprContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#CheckOrExpr.
    def enterCheckOrExpr(self, ctx:SMILE_GeneralizedParser.CheckOrExprContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#CheckOrExpr.
    def exitCheckOrExpr(self, ctx:SMILE_GeneralizedParser.CheckOrExprContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#CheckNotExpr.
    def enterCheckNotExpr(self, ctx:SMILE_GeneralizedParser.CheckNotExprContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#CheckNotExpr.
    def exitCheckNotExpr(self, ctx:SMILE_GeneralizedParser.CheckNotExprContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#CheckRawExpr.
    def enterCheckRawExpr(self, ctx:SMILE_GeneralizedParser.CheckRawExprContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#CheckRawExpr.
    def exitCheckRawExpr(self, ctx:SMILE_GeneralizedParser.CheckRawExprContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#CmpAtom.
    def enterCmpAtom(self, ctx:SMILE_GeneralizedParser.CmpAtomContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#CmpAtom.
    def exitCmpAtom(self, ctx:SMILE_GeneralizedParser.CmpAtomContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#InAtom.
    def enterInAtom(self, ctx:SMILE_GeneralizedParser.InAtomContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#InAtom.
    def exitInAtom(self, ctx:SMILE_GeneralizedParser.InAtomContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#BetweenAtom.
    def enterBetweenAtom(self, ctx:SMILE_GeneralizedParser.BetweenAtomContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#BetweenAtom.
    def exitBetweenAtom(self, ctx:SMILE_GeneralizedParser.BetweenAtomContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#RegexAtom.
    def enterRegexAtom(self, ctx:SMILE_GeneralizedParser.RegexAtomContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#RegexAtom.
    def exitRegexAtom(self, ctx:SMILE_GeneralizedParser.RegexAtomContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#IsNullAtom.
    def enterIsNullAtom(self, ctx:SMILE_GeneralizedParser.IsNullAtomContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#IsNullAtom.
    def exitIsNullAtom(self, ctx:SMILE_GeneralizedParser.IsNullAtomContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#IsNotNullAtom.
    def enterIsNotNullAtom(self, ctx:SMILE_GeneralizedParser.IsNotNullAtomContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#IsNotNullAtom.
    def exitIsNotNullAtom(self, ctx:SMILE_GeneralizedParser.IsNotNullAtomContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#cmpOp.
    def enterCmpOp(self, ctx:SMILE_GeneralizedParser.CmpOpContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#cmpOp.
    def exitCmpOp(self, ctx:SMILE_GeneralizedParser.CmpOpContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#literalList.
    def enterLiteralList(self, ctx:SMILE_GeneralizedParser.LiteralListContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#literalList.
    def exitLiteralList(self, ctx:SMILE_GeneralizedParser.LiteralListContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#delete_gen.
    def enterDelete_gen(self, ctx:SMILE_GeneralizedParser.Delete_genContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#delete_gen.
    def exitDelete_gen(self, ctx:SMILE_GeneralizedParser.Delete_genContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#propertyDelete.
    def enterPropertyDelete(self, ctx:SMILE_GeneralizedParser.PropertyDeleteContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#propertyDelete.
    def exitPropertyDelete(self, ctx:SMILE_GeneralizedParser.PropertyDeleteContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#foreignKeyDelete.
    def enterForeignKeyDelete(self, ctx:SMILE_GeneralizedParser.ForeignKeyDeleteContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#foreignKeyDelete.
    def exitForeignKeyDelete(self, ctx:SMILE_GeneralizedParser.ForeignKeyDeleteContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#embeddedDelete.
    def enterEmbeddedDelete(self, ctx:SMILE_GeneralizedParser.EmbeddedDeleteContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#embeddedDelete.
    def exitEmbeddedDelete(self, ctx:SMILE_GeneralizedParser.EmbeddedDeleteContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#entityDelete.
    def enterEntityDelete(self, ctx:SMILE_GeneralizedParser.EntityDeleteContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#entityDelete.
    def exitEntityDelete(self, ctx:SMILE_GeneralizedParser.EntityDeleteContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#keyDelete.
    def enterKeyDelete(self, ctx:SMILE_GeneralizedParser.KeyDeleteContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#keyDelete.
    def exitKeyDelete(self, ctx:SMILE_GeneralizedParser.KeyDeleteContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#labelDelete.
    def enterLabelDelete(self, ctx:SMILE_GeneralizedParser.LabelDeleteContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#labelDelete.
    def exitLabelDelete(self, ctx:SMILE_GeneralizedParser.LabelDeleteContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#constraintDelete.
    def enterConstraintDelete(self, ctx:SMILE_GeneralizedParser.ConstraintDeleteContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#constraintDelete.
    def exitConstraintDelete(self, ctx:SMILE_GeneralizedParser.ConstraintDeleteContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#rename_gen.
    def enterRename_gen(self, ctx:SMILE_GeneralizedParser.Rename_genContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#rename_gen.
    def exitRename_gen(self, ctx:SMILE_GeneralizedParser.Rename_genContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#propertyRename.
    def enterPropertyRename(self, ctx:SMILE_GeneralizedParser.PropertyRenameContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#propertyRename.
    def exitPropertyRename(self, ctx:SMILE_GeneralizedParser.PropertyRenameContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#entityRename.
    def enterEntityRename(self, ctx:SMILE_GeneralizedParser.EntityRenameContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#entityRename.
    def exitEntityRename(self, ctx:SMILE_GeneralizedParser.EntityRenameContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#keyType.
    def enterKeyType(self, ctx:SMILE_GeneralizedParser.KeyTypeContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#keyType.
    def exitKeyType(self, ctx:SMILE_GeneralizedParser.KeyTypeContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#keyClause.
    def enterKeyClause(self, ctx:SMILE_GeneralizedParser.KeyClauseContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#keyClause.
    def exitKeyClause(self, ctx:SMILE_GeneralizedParser.KeyClauseContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#referencesClause.
    def enterReferencesClause(self, ctx:SMILE_GeneralizedParser.ReferencesClauseContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#referencesClause.
    def exitReferencesClause(self, ctx:SMILE_GeneralizedParser.ReferencesClauseContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#withColumnsClause.
    def enterWithColumnsClause(self, ctx:SMILE_GeneralizedParser.WithColumnsClauseContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#withColumnsClause.
    def exitWithColumnsClause(self, ctx:SMILE_GeneralizedParser.WithColumnsClauseContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#identifierList.
    def enterIdentifierList(self, ctx:SMILE_GeneralizedParser.IdentifierListContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#identifierList.
    def exitIdentifierList(self, ctx:SMILE_GeneralizedParser.IdentifierListContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#flatten_gen.
    def enterFlatten_gen(self, ctx:SMILE_GeneralizedParser.Flatten_genContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#flatten_gen.
    def exitFlatten_gen(self, ctx:SMILE_GeneralizedParser.Flatten_genContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#unflatten_gen.
    def enterUnflatten_gen(self, ctx:SMILE_GeneralizedParser.Unflatten_genContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#unflatten_gen.
    def exitUnflatten_gen(self, ctx:SMILE_GeneralizedParser.Unflatten_genContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#unnest_gen.
    def enterUnnest_gen(self, ctx:SMILE_GeneralizedParser.Unnest_genContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#unnest_gen.
    def exitUnnest_gen(self, ctx:SMILE_GeneralizedParser.Unnest_genContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#unnestCarryList.
    def enterUnnestCarryList(self, ctx:SMILE_GeneralizedParser.UnnestCarryListContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#unnestCarryList.
    def exitUnnestCarryList(self, ctx:SMILE_GeneralizedParser.UnnestCarryListContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#unnestCarryField.
    def enterUnnestCarryField(self, ctx:SMILE_GeneralizedParser.UnnestCarryFieldContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#unnestCarryField.
    def exitUnnestCarryField(self, ctx:SMILE_GeneralizedParser.UnnestCarryFieldContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#unnestFieldList.
    def enterUnnestFieldList(self, ctx:SMILE_GeneralizedParser.UnnestFieldListContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#unnestFieldList.
    def exitUnnestFieldList(self, ctx:SMILE_GeneralizedParser.UnnestFieldListContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#SimpleField.
    def enterSimpleField(self, ctx:SMILE_GeneralizedParser.SimpleFieldContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#SimpleField.
    def exitSimpleField(self, ctx:SMILE_GeneralizedParser.SimpleFieldContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#NestedField.
    def enterNestedField(self, ctx:SMILE_GeneralizedParser.NestedFieldContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#NestedField.
    def exitNestedField(self, ctx:SMILE_GeneralizedParser.NestedFieldContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#unwind_gen.
    def enterUnwind_gen(self, ctx:SMILE_GeneralizedParser.Unwind_genContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#unwind_gen.
    def exitUnwind_gen(self, ctx:SMILE_GeneralizedParser.Unwind_genContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#wind_gen.
    def enterWind_gen(self, ctx:SMILE_GeneralizedParser.Wind_genContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#wind_gen.
    def exitWind_gen(self, ctx:SMILE_GeneralizedParser.Wind_genContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#nest_gen.
    def enterNest_gen(self, ctx:SMILE_GeneralizedParser.Nest_genContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#nest_gen.
    def exitNest_gen(self, ctx:SMILE_GeneralizedParser.Nest_genContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#copy_gen.
    def enterCopy_gen(self, ctx:SMILE_GeneralizedParser.Copy_genContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#copy_gen.
    def exitCopy_gen(self, ctx:SMILE_GeneralizedParser.Copy_genContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#propertyCopy.
    def enterPropertyCopy(self, ctx:SMILE_GeneralizedParser.PropertyCopyContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#propertyCopy.
    def exitPropertyCopy(self, ctx:SMILE_GeneralizedParser.PropertyCopyContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#entityCopy.
    def enterEntityCopy(self, ctx:SMILE_GeneralizedParser.EntityCopyContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#entityCopy.
    def exitEntityCopy(self, ctx:SMILE_GeneralizedParser.EntityCopyContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#move_gen.
    def enterMove_gen(self, ctx:SMILE_GeneralizedParser.Move_genContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#move_gen.
    def exitMove_gen(self, ctx:SMILE_GeneralizedParser.Move_genContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#merge_gen.
    def enterMerge_gen(self, ctx:SMILE_GeneralizedParser.Merge_genContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#merge_gen.
    def exitMerge_gen(self, ctx:SMILE_GeneralizedParser.Merge_genContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#split_gen.
    def enterSplit_gen(self, ctx:SMILE_GeneralizedParser.Split_genContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#split_gen.
    def exitSplit_gen(self, ctx:SMILE_GeneralizedParser.Split_genContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#splitPartGen.
    def enterSplitPartGen(self, ctx:SMILE_GeneralizedParser.SplitPartGenContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#splitPartGen.
    def exitSplitPartGen(self, ctx:SMILE_GeneralizedParser.SplitPartGenContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#cast_gen.
    def enterCast_gen(self, ctx:SMILE_GeneralizedParser.Cast_genContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#cast_gen.
    def exitCast_gen(self, ctx:SMILE_GeneralizedParser.Cast_genContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#propertyCast.
    def enterPropertyCast(self, ctx:SMILE_GeneralizedParser.PropertyCastContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#propertyCast.
    def exitPropertyCast(self, ctx:SMILE_GeneralizedParser.PropertyCastContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#constraintCast.
    def enterConstraintCast(self, ctx:SMILE_GeneralizedParser.ConstraintCastContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#constraintCast.
    def exitConstraintCast(self, ctx:SMILE_GeneralizedParser.ConstraintCastContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#entityCast.
    def enterEntityCast(self, ctx:SMILE_GeneralizedParser.EntityCastContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#entityCast.
    def exitEntityCast(self, ctx:SMILE_GeneralizedParser.EntityCastContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#recard_gen.
    def enterRecard_gen(self, ctx:SMILE_GeneralizedParser.Recard_genContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#recard_gen.
    def exitRecard_gen(self, ctx:SMILE_GeneralizedParser.Recard_genContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#transform_gen.
    def enterTransform_gen(self, ctx:SMILE_GeneralizedParser.Transform_genContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#transform_gen.
    def exitTransform_gen(self, ctx:SMILE_GeneralizedParser.Transform_genContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#TransformToRelationship.
    def enterTransformToRelationship(self, ctx:SMILE_GeneralizedParser.TransformToRelationshipContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#TransformToRelationship.
    def exitTransformToRelationship(self, ctx:SMILE_GeneralizedParser.TransformToRelationshipContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#TransformToEntity.
    def enterTransformToEntity(self, ctx:SMILE_GeneralizedParser.TransformToEntityContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#TransformToEntity.
    def exitTransformToEntity(self, ctx:SMILE_GeneralizedParser.TransformToEntityContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#withCardinalityClause.
    def enterWithCardinalityClause(self, ctx:SMILE_GeneralizedParser.WithCardinalityClauseContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#withCardinalityClause.
    def exitWithCardinalityClause(self, ctx:SMILE_GeneralizedParser.WithCardinalityClauseContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#usingKeyClause.
    def enterUsingKeyClause(self, ctx:SMILE_GeneralizedParser.UsingKeyClauseContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#usingKeyClause.
    def exitUsingKeyClause(self, ctx:SMILE_GeneralizedParser.UsingKeyClauseContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#whereClause.
    def enterWhereClause(self, ctx:SMILE_GeneralizedParser.WhereClauseContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#whereClause.
    def exitWhereClause(self, ctx:SMILE_GeneralizedParser.WhereClauseContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#withPropertiesClause.
    def enterWithPropertiesClause(self, ctx:SMILE_GeneralizedParser.WithPropertiesClauseContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#withPropertiesClause.
    def exitWithPropertiesClause(self, ctx:SMILE_GeneralizedParser.WithPropertiesClauseContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#propertyDefList.
    def enterPropertyDefList(self, ctx:SMILE_GeneralizedParser.PropertyDefListContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#propertyDefList.
    def exitPropertyDefList(self, ctx:SMILE_GeneralizedParser.PropertyDefListContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#propertyDef.
    def enterPropertyDef(self, ctx:SMILE_GeneralizedParser.PropertyDefContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#propertyDef.
    def exitPropertyDef(self, ctx:SMILE_GeneralizedParser.PropertyDefContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#cardinalityType.
    def enterCardinalityType(self, ctx:SMILE_GeneralizedParser.CardinalityTypeContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#cardinalityType.
    def exitCardinalityType(self, ctx:SMILE_GeneralizedParser.CardinalityTypeContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#constraintKeyType.
    def enterConstraintKeyType(self, ctx:SMILE_GeneralizedParser.ConstraintKeyTypeContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#constraintKeyType.
    def exitConstraintKeyType(self, ctx:SMILE_GeneralizedParser.ConstraintKeyTypeContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#dataType.
    def enterDataType(self, ctx:SMILE_GeneralizedParser.DataTypeContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#dataType.
    def exitDataType(self, ctx:SMILE_GeneralizedParser.DataTypeContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#qualifiedName.
    def enterQualifiedName(self, ctx:SMILE_GeneralizedParser.QualifiedNameContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#qualifiedName.
    def exitQualifiedName(self, ctx:SMILE_GeneralizedParser.QualifiedNameContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#pathSegment.
    def enterPathSegment(self, ctx:SMILE_GeneralizedParser.PathSegmentContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#pathSegment.
    def exitPathSegment(self, ctx:SMILE_GeneralizedParser.PathSegmentContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#identifier.
    def enterIdentifier(self, ctx:SMILE_GeneralizedParser.IdentifierContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#identifier.
    def exitIdentifier(self, ctx:SMILE_GeneralizedParser.IdentifierContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#condition.
    def enterCondition(self, ctx:SMILE_GeneralizedParser.ConditionContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#condition.
    def exitCondition(self, ctx:SMILE_GeneralizedParser.ConditionContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#equalityOnlyCondition.
    def enterEqualityOnlyCondition(self, ctx:SMILE_GeneralizedParser.EqualityOnlyConditionContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#equalityOnlyCondition.
    def exitEqualityOnlyCondition(self, ctx:SMILE_GeneralizedParser.EqualityOnlyConditionContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#equalityCondition.
    def enterEqualityCondition(self, ctx:SMILE_GeneralizedParser.EqualityConditionContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#equalityCondition.
    def exitEqualityCondition(self, ctx:SMILE_GeneralizedParser.EqualityConditionContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#edgeCondition.
    def enterEdgeCondition(self, ctx:SMILE_GeneralizedParser.EdgeConditionContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#edgeCondition.
    def exitEdgeCondition(self, ctx:SMILE_GeneralizedParser.EdgeConditionContext):
        pass


    # Enter a parse tree produced by SMILE_GeneralizedParser#literal.
    def enterLiteral(self, ctx:SMILE_GeneralizedParser.LiteralContext):
        pass

    # Exit a parse tree produced by SMILE_GeneralizedParser#literal.
    def exitLiteral(self, ctx:SMILE_GeneralizedParser.LiteralContext):
        pass



del SMILE_GeneralizedParser